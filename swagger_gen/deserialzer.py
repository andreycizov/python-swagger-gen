import uuid
from enum import Enum
from functools import partial
from importlib import import_module
from typing import NamedTuple, Any, List, _ForwardRef, _FinalTypingBase, _type_check, Optional, Union, Dict, Callable, \
    _tp_cache


class DeserializerNode(NamedTuple):
    type: Any
    deps: List[Any]


ATOMS = (int, str, bool)


class _Joint(_FinalTypingBase, _root=True):
    """Joint type.

    Joint[X] is equivalent to Union[X, _Joint.Tag].
    """

    __slots__ = ()

    class Tag:
        pass

    @_tp_cache
    def __getitem__(self, arg):
        arg = _type_check(arg, "Joint[t] requires a single type.")
        return Union[arg, self.Tag]


Joint = _Joint(_root=True)


def _generate_type_deserializer_step(t, mod) -> DeserializerNode:
    def _norm_type(t):
        # the problem of type normalisation with cyclic references is the fact
        # that we can't normalize types at all, somehow ?
        if isinstance(t, _ForwardRef):
            # todo: we need to know which globals to use for it
            t = t._eval_type(mod.__dict__, mod.__dict__)
            t = _norm_type(t)
            return t
        elif t.__class__.__name__ == '_Union':
            if t.__args__[-1] == type(None):
                *vt, _ = t.__args__
                return Optional[_norm_type(Union[tuple(_norm_type(vtt) for vtt in vt)])]
            elif t.__args__[-1] == _Joint.Tag:
                *vt, _ = t.__args__
                return Joint[_norm_type(Union[tuple(_norm_type(vtt) for vtt in vt)])]
            else:
                st = [_norm_type(x) for x in t.__args__]
                return Union[st]
        elif t in ATOMS:
            return t
        elif issubclass(t, type(None)):
            return t
        elif issubclass(t, uuid.UUID):
            return t
        elif issubclass(t, List):
            assert hasattr(t, '__args__')
            st, = t.__args__
            st = _norm_type(st)
            return List[st]
        elif issubclass(t, Dict):
            kt, vt = t.__args__
            kt, vt = _norm_type(kt), _norm_type(vt)
            return Dict[kt, vt]
        elif issubclass(t, Enum):
            return t
        elif hasattr(t, 'deserializer'):
            assert False
        elif hasattr(t, '_field_types'):
            # NamedTuple meta
            return t
        else:
            raise NotImplementedError(f'{t}')

    if isinstance(t, _ForwardRef):
        # todo: we need to know which globals to use for it
        return _generate_type_deserializer_step(_norm_type(t))
    elif t.__class__.__name__ == '_Union':
        assert hasattr(t, '__args__')

        # todo build all of the dependencies that would later on be used in the deserializer

        sub_args = t.__args__

        if sub_args[-1] == type(None):
            *vt, _ = t.__args__
            vt = tuple(vt)

            if len(vt) == 1:
                vt = _norm_type(vt[0])

                return DeserializerNode(t, [vt])
            else:
                vt = _norm_type(Union[vt])
                r = _generate_type_deserializer_step(vt, mod)
                return DeserializerNode(t, r.deps)
        elif sub_args[-1] == _Joint.Tag:
            *vt, _ = t.__args__
            vt = tuple(vt)
            if len(vt) == 1:
                vt = _norm_type(vt[0])

                fields = [z for i, (f, z) in enumerate(vt._field_types.items())]

                rtn_deps = [_norm_type(z) for z in fields]

                return DeserializerNode(t, rtn_deps)
            else:
                assert False
        elif len(sub_args) == 1:
            assert False, [2]
        else:
            assert False, [1]

        rtn_deps = []

        while True:

            if sub_args[-1] == type(None):
                *vt, _ = t.__args__
                vt = tuple(vt)
                vt = _norm_type(vt)
                rtn_deps = [vt]
            elif sub_args[-1] == _Joint.Tag:
                *vt, _ = t.__args__
                vt = tuple(vt)
                vt = _norm_type(Union[vt])

                fields = [z for i, (f, z) in enumerate(vt._field_types.items())]

                rtn_deps = [_norm_type(z) for z in fields]

                return DeserializerNode(t, rtn_deps)
            elif len(sub_args) == 1:
                pass
                break
            else:
                assert False

        return DeserializerNode(t, rtn_deps)
    elif t in ATOMS:
        return DeserializerNode(t, [])
    elif issubclass(t, type(None)):
        return DeserializerNode(t, [])
    elif issubclass(t, uuid.UUID):
        return DeserializerNode(t, [])
    elif issubclass(t, List):
        assert hasattr(t, '__args__')
        st, = t.__args__
        st = _norm_type(st)
        return DeserializerNode(List[st], [st])
    elif issubclass(t, Dict):
        kt, vt = t.__args__
        kt, vt = _norm_type(kt), _norm_type(vt)
        return DeserializerNode(Dict[kt, vt], [kt, vt])
    elif issubclass(t, Enum):
        return DeserializerNode(t, [])
    elif hasattr(t, 'deserializer'):
        assert False
    elif hasattr(t, '_field_types'):
        # NamedTuple meta
        return DeserializerNode(t, [_norm_type(t) for f, t in t._field_types.items()])
    else:
        raise NotImplementedError(f'{t}')


def _generate_type_deserializer_walk(t) -> List[DeserializerNode]:
    mod = import_module(t.__module__)

    x = _generate_type_deserializer_step(t, mod)

    visited: Dict[Any, DeserializerNode] = {}
    visited[x.type] = x

    to_visit = [y for y in x.deps if y not in visited]

    while len(to_visit):
        x = to_visit.pop()

        x = _generate_type_deserializer_step(x, mod)

        visited[x.type] = x

        to_visit = [y for y in x.deps if y not in visited and y not in to_visit] + to_visit
        to_visit = list(set(to_visit))

    return list(visited.values())


def _generate_type_deserializer_merge(*xs: List[DeserializerNode]):
    r: List[DeserializerNode] = []

    for x in xs:
        for y in x:
            for rx in r:
                if rx.type == y.type:
                    break
            else:
                r.append(y)

    return r


DeserializerStruct = Dict[Any, List[Callable[[dict], Any]]]
DeserializerDict = Dict[Any, Callable[[dict], Any]]


def _generate_deserializer_struct(g: List[DeserializerNode]) -> DeserializerStruct:
    r = {}

    def raiser(val: dict) -> Any:
        assert False, 'should never happen'

    for x in g:
        r[x.type] = [raiser for _ in x.deps]

    return r


def _generate_deserializer(t, deps):
    # deps need to be created beforehands, but they will be empty at first
    if t.__class__.__name__ == '_Union':
        assert hasattr(t, '__args__')

        sub_args = t.__args__

        funcs_to = []

        while True:
            if sub_args[-1] == type(None):
                vt, *_ = sub_args

                def deser_none(val, fn):
                    return fn(val) if val is not None else None

                funcs_to.append(deser_none)
                sub_args = sub_args[:-1]
            elif sub_args[-1] == _Joint.Tag:
                vt, *_ = sub_args
                fields = [(i, f) for i, (f, _) in enumerate(vt._field_types.items())]

                def deser_joint(val, fn):
                    r = {}
                    i, f = None, None
                    try:
                        for i, f in fields:
                            r[f] = deps[i](val)
                    except BaseException as e:
                        raise NotImplementedError(f'{t} {i} {f} {e}')
                    return vt(**r)

                funcs_to.append(deser_joint)
                sub_args = sub_args[:-1]
                break
            elif len(sub_args) == 1:
                vt, *_ = sub_args

                def deser_value(val, fn):
                    return deps[0](val)

                funcs_to.append(deser_value)
                break
            else:
                assert False, ('possibly a union type', t, t.__args__, deps)

        def central_dummy(val):
            return val

        prev_item = central_dummy
        for x in funcs_to[::-1]:
            prev_item = partial(x, fn=prev_item)

        def central(val):
            return prev_item(val=val)

        return central
    elif t in ATOMS:
        return lambda val: val
    elif issubclass(t, type(None)):
        return lambda _: None
    elif issubclass(t, uuid.UUID):
        return lambda val: uuid.UUID(hex=val)

    elif issubclass(t, List):
        assert hasattr(t, '__args__')

        def deser_list(val):
            r = []
            i = None
            try:
                for i, v in enumerate(val):
                    r.append(deps[0](v))
            except BaseException as e:
                raise NotImplementedError(f'{t} {i} {e}')
            return r

        return deser_list
    elif issubclass(t, Dict):

        def deser_dict(val):
            r = {}
            try:
                for k, v in val.items():
                    r[deps[0](k)] = deps[1](v)
            except BaseException as e:
                raise NotImplementedError(f'{t} {k} {v} {e}')
            return r

        return deser_dict
    elif issubclass(t, Enum):
        return lambda val: t[val]
    elif hasattr(t, 'deserializer'):
        assert False
    elif hasattr(t, '_field_types'):
        # NamedTuple meta
        fields = [f for f, _ in t._field_types.items()]

        def deser_namedtuple(val):
            r = {}

            i, f = None, None

            try:

                for i, f in enumerate(fields):
                    r[f] = deps[i](val.get(f))
            except BaseException as e:
                raise ValueError(f'[1] {t}, {i}, {f}, {val}: {e}')

            try:

                return t(**r)
            except BaseException as e:
                raise ValueError(f'[2] {t}, {i}, {f}, {val}: {e}')

        return deser_namedtuple
    else:
        raise NotImplementedError(f'{t}')


def _populate_deserializer_struct(g: List[DeserializerNode], s: DeserializerStruct) -> DeserializerDict:
    r = {}

    for t, deps in s.items():
        r[t] = _generate_deserializer(t, deps)

    for n, (t, deps) in zip(g, s.items()):
        assert len(n.deps) == len(deps), (n.deps, deps)
        for dt, i in zip(n.deps, range(len(deps))):
            deps[i] = r[dt]

    return r


def deserialize(d: DeserializerDict, t, val):
    return d[t](val)
