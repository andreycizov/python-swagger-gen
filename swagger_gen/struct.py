from typing import NamedTuple, Dict, Optional, List

from swagger_gen.deserialzer import Joint, _generate_type_deserializer_merge, _generate_type_deserializer_walk, \
    _populate_deserializer_struct, _generate_deserializer_struct

Authorizations = Dict[str, str]


class Parameter(NamedTuple):
    paramType: str
    """Required. The type of the parameter (that is, the location of the parameter in the request). The value MUST be one of these values: "path", "query", "body", "header", "form". Note that the values MUST be lower case."""
    name: str
    """Required. The unique name for the parameter. Each name MUST be unique, even if they are associated with different paramType values. Parameter names are case sensitive.
    If paramType is "path", the name field MUST correspond to the associated path segment from the path field in the API Object.
    If paramType is "query", the name field corresponds to the query parameter name.
    If paramType is "body", the name is used only for Swagger-UI and Swagger-Codegen. In this case, the name MUST be "body".
    If paramType is "form", the name field corresponds to the form parameter key.
    If paramType is "header", the name field corresponds to the header parameter key.
    See here for some examples."""
    description: Optional[str]
    """Recommended. A brief description of this parameter."""
    required: bool
    """A flag to note whether this parameter is required. If this field is not included, it is equivalent to adding this field with the value false. If paramType is "path" then this field MUST be included and have the value true."""
    allowMultiple: bool
    """Another way to allow multiple values for a "query" parameter. If used, the query parameter may accept comma-separated values. The field may be used only if paramType is "query", "header" or "path"."""


class ResponseMessage(NamedTuple):
    code: int
    """Required. The HTTP status code returned. The value SHOULD be one of the status codes as described in RFC 2616 - Section 10."""
    message: str
    """Required. The explanation for the status code. It SHOULD be the reason an error is received if an error status code is used."""
    responseModel: str
    """The return type for the given response."""


class Operation(NamedTuple):
    method: str
    """Required. The HTTP method required to invoke this operation. The value MUST be one of the following values: "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS". The values MUST be in uppercase."""
    summary: str
    """A short summary of what the operation does. For maximum readability in the swagger-ui, this field SHOULD be less than 120 characters."""
    notes: str
    """A verbose explanation of the operation behavior."""
    nickname: str
    """Required. A unique id for the operation that can be used by tools reading the output for further and easier manipulation. For example, Swagger-Codegen will use the nickname as the method name of the operation in the client it generates. The value MUST be alphanumeric and may include underscores. Whitespace characters are not allowed."""
    type: str
    """<GL> response type"""
    authorizations: Optional[Authorizations]
    """A list of authorizations required to execute this operation. While not mandatory, if used, it overrides the value given at the API Declaration's authorizations. In order to completely remove API Declaration's authorizations completely, an empty object ({}) may be applied."""
    parameters: Optional[List[Parameter]]
    """Required. The inputs to the operation. If no parameters are needed, an empty array MUST be included."""
    responseMessages: List[ResponseMessage]
    """Lists the possible response statuses that can return from the operation."""
    produces: Optional[List[str]]
    """A list of MIME types this operation can produce. This is overrides the global produces definition at the root of the API Declaration. Each string value SHOULD represent a MIME type."""
    consumes: Optional[List[str]]
    """A list of MIME types this operation can consume. This is overrides the global consumes definition at the root of the API Declaration. Each string value SHOULD represent a MIME type."""
    deprecated: str
    """Declares this operation to be deprecated. Usage of the declared operation should be refrained. Valid value MUST be either "true" or "false". Note: This field will change to type boolean in the future."""


class API(NamedTuple):
    path: str
    """Required. The relative path to the operation, from the basePath, which this operation describes. The value SHOULD be in a relative (URL) path format."""
    name: Optional[str]
    """<Graylog>"""
    description: Optional[str]
    """Recommended. A short description of the resource."""
    operations: Optional[List[Operation]]
    """Required. A list of the API operations available on this path. The array may include 0 or more operations. There MUST NOT be more than one Operation Object per method in the array."""


class PropertySub(NamedTuple):
    type: str
    """Any"""
    # $ref: str
    """Any"""
    format: str
    """primitive"""


class PropertyExt(NamedTuple):
    defaultValue: Optional[Dict[str, str]]
    """primitive"""
    enum: Optional[List[str]]
    """string"""
    minimum: str
    """number, integer"""
    maximum: str
    """number, integer"""
    items: Optional['JointProperty']
    """array"""
    uniqueItems: bool
    """array"""
    properties: Optional[Dict[str, 'JointProperty']]
    """Required. A list of properties (fields) that are part of the model"""
    additional_properties: Optional['JointProperty']


class Property(NamedTuple):
    sub: PropertySub
    ext: PropertyExt


JointProperty = Joint[Property]

Properties = Dict[str, JointProperty]


class Model(NamedTuple):
    id: str
    """Required. A unique identifier for the model. This MUST be the name given to {Model Name}."""
    description: str
    """A brief description of this model."""
    required: Optional[List[str]]
    """A definition of which properties MUST exist when a model instance is produced. The values MUST be the {Property Name} of one of the properties."""
    properties: Properties
    """Required. A list of properties (fields) that are part of the model"""

    subTypes: Optional[List[str]]
    """List of the model ids that inherit from this model. Sub models inherit all the properties of the parent model. Since inheritance is transitive, if the parent of a model inherits from another model, its sub-model will include all properties. As such, if you have Foo->Bar->Baz, then Baz will inherit the properties of Bar and Foo. There MUST NOT be a cyclic definition of inheritance. For example, if Foo -> ... -> Bar, having Bar -> ... -> Foo is not allowed. There also MUST NOT be a case of multiple inheritance. For example, Foo -> Baz <- Bar is not allowed. A sub-model definition MUST NOT override the properties of any of its ancestors. All sub-models MUST be defined in the same API Declaration."""
    discriminator: str
    """MUST be included only if subTypes is included. This field allows for polymorphism within the described inherited models. This field MAY be included at any base model but MUST NOT be included in a sub-model. The value of this field MUST be a name of one of the properties in this model, and that field MUST be in the required list. When used, the value of the discriminator property MUST be the name of the parent model or any of its sub-models (to any depth of inheritance)."""


Models = Dict[str, Model]
APIs = List[API]


class Definition(NamedTuple):
    apiVersion: str
    swaggerVersion: str
    basePath: Optional[str]
    resourcePath: Optional[str]
    apis: Optional[APIs]
    models: Optional[Models]


DESERIALIZER_LIST = _generate_type_deserializer_merge(
    _generate_type_deserializer_walk(Definition)
)

DESERIALIZER_STRUCT = _populate_deserializer_struct(
    DESERIALIZER_LIST, _generate_deserializer_struct(DESERIALIZER_LIST)
)


