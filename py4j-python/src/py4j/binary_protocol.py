# -*- coding: UTF-8 -*-
"""
The binary protocol module defines the primitives used by the Py4J protocol.

The types and commands are represented as signed short (-32768 to 32767) and
negative numbers are reserved for custom types and commands implemented by
users.

References are signed longs, but the protocol will eventually be able to
support UUIDs. Negative numbers are reserved for special cases.
"""

from collections import deque, defaultdict, namedtuple
from decimal import Decimal
import io
from struct import pack, unpack

from py4j.compat import (
    long, bytestrrepr, basestring, unicode)
from py4j.protocol import Py4JError, Py4JProtocolError


DEFAULT_STRING_ENCODING = "utf-8"

DEFAULT_BYTESTRING_ENCODING = "ascii"

DEFAULT_SIZE_PACK_FORMAT = "!i"

DEFAULT_SIZE_BYTES_SIZE = 4

JAVA_MAX_INT = 2147483647
JAVA_MIN_INT = -2147483648

JAVA_INFINITY = "Infinity"
JAVA_NEGATIVE_INFINITY = "-Infinity"
JAVA_NAN = "NaN"

# ENTRY POINTS LONG
ENTRY_POINT_OBJECT_ID_LONG = -1
SERVER_OBJECT_ID_LONG = -2

CANNOT_ENCODE = object()

LONG_ID_MODE = "LONG_ID_MODE"
UUID_ID_MODE = "UUID_ID_MODE"


class LongReferenceType(object):

    ENTRY_POINT_OBJECT_ID = ENTRY_POINT_OBJECT_ID_LONG

    SERVER_OBJECT_ID = SERVER_OBJECT_ID_LONG


# Basic Types (0-10)
JAVA_REFERENCE_LONG_TYPE = 0
JAVA_REFERENCE_UUID_TYPE = 1
PYTHON_REFERENCE_LONG_TYPE = 2
PYTHON_REFERENCE_UUID_TYPE = 3
VOID_TYPE = 4
NULL_TYPE = 5
BOOLEAN_TRUE_TYPE = 6
BOOLEAN_FALSE_TYPE = 7

# Int types (10-20)
BYTES_TYPE = 10
INTEGER_TYPE = 12
LONG_TYPE = 13
DOUBLE_TYPE = 15
DECIMAL_TYPE = 16

# String types (20-30)
STRING_TYPE = 20

# Collection types (30-50)
ARRAY_TYPE = 30
ITERATOR_TYPE = 31
LIST_TYPE = 32
SET_TYPE = 33
MAP_TYPE = 34

# Py4J Types (50-70)
PACKAGE_TYPE = 50
CLASS_TYPE = 51
METHOD_TYPE = 52
NO_MEMBER = 53

# Protocol Types (70-90)
ERROR_TYPE = 70
SUCCESS_TYPE = 71
RETURN_TYPE = 72
COMMAND_TYPE = 73
END_TYPE = 77

# Python types that depend on Python 2 and 3 differences

SUPPORTED_STRING_TYPES = [unicode]
# For python 2
if unicode != str:
    SUPPORTED_STRING_TYPES.append(str)
# For python 2
if basestring != unicode:
    SUPPORTED_STRING_TYPES.append(basestring)

SUPPORTED_BYTE_TYPES = [bytearray]
# For python 3
if bytes != str:
    SUPPORTED_BYTE_TYPES.append(bytes)

SUPPORTED_INT_TYPES = [int]
# For python 2
if int != long:
    SUPPORTED_INT_TYPES.append(long)

SUPPORTED_NONE_TYPES = [type(None)]


# Commands (1-20)
CALL_COMMAND = 0
CONSTRUCTOR_COMMAND = 1
SHUTDOWN_GATEWAY = 2
# TODO
STREAM_COMMAND = 3

# Array
ARRAY_GET_SUB_COMMAND = 20
ARRAY_SET_SUB_COMMAND = 21
ARRAY_SLICE_SUB_COMMAND = 22
ARRAY_LEN_SUB_COMMAND = 23
ARRAY_CREATE_SUB_COMMAND = 24

# List
LIST_SORT_SUBCOMMAND = 30
LIST_REVERSE_SUBCOMMAND = 31
LIST_SLICE_SUBCOMMAND = 32
LIST_CONCAT_SUBCOMMAND = 33
LIST_MULT_SUBCOMMAND = 34
LIST_IMULT_SUBCOMMAND = 35
LIST_COUNT_SUBCOMMAND = 36

# Fields
FIELD_GET_SUBCOMMAND = 40
FIELD_SET_SUBCOMMAND = 41

# Memory
MEMORY_DEL_SUBCOMMAND = 50
MEMORY_ATTACH_SUBCOMMAND = 51

# Help
HELP_OBJECT_SUBCOMMAND = 60
HELP_CLASS_SUBCOMMAND = 61

# Dir
DIR_FIELDS_SUBCOMMAND = 70
DIR_METHODS_SUBCOMMAND = 71
DIR_STATIC_SUBCOMMAND = 72
DIR_JVMVIEW_SUBCOMMAND = 73

# Reflection
REFL_GET_UNKNOWN_SUB_COMMAND = 80
REFL_GET_MEMBER_SUB_COMMAND = 81
REFL_GET_JAVA_LANG_CLASS_SUB_COMMAND = 82

JVM_CREATE_VIEW_SUB_COMMAND = 90
JVM_IMPORT_SUB_COMMAND = 91
JVM_SEARCH_SUB_COMMAND = 92
REMOVE_IMPORT_SUB_COMMAND = 93

# Python server commands
PYTHON_CALL_COMMAND = 100


DecodedArgument = namedtuple("DecodedArgument", ["type", "value"])

EncodedArgument = namedtuple("EncodedArgument", ["type", "size", "value"])

END_DECODED_ARGUMENT = DecodedArgument(END_TYPE, None)

END_ENCODED_ARGUMENT = EncodedArgument(END_TYPE, None, None)


class DecoderRegistry(object):
    """Registry that holds all possible decoders used to decode Py4J arguments
    to Python arguments.

    This class is not thread-safe: if multiple thread tries to register
    decoders at the same time, concurrent modification errors may be raised.

    Multiple threads can call de decode methods though if they are not
    registering decoders at the same time.
    """

    def __init__(
            self, string_encoding=DEFAULT_STRING_ENCODING,
            id_mode=LONG_ID_MODE):
        self.type_decoders = {}
        self.string_encoding = string_encoding
        self.id_mode = id_mode

    @classmethod
    def get_default_decoder_registry(
            cls, string_encoding=DEFAULT_STRING_ENCODING,
            id_mode=LONG_ID_MODE):
        registry = cls(string_encoding=string_encoding, id_mode=id_mode)
        for decoder_cls in DEFAULT_DECODERS:
            registry.register_decoder(decoder_cls())
        return registry

    def add_java_collection_decoders(self):
        """TODO
        """
        pass

    def register_decoder(self, decoder, force=False):
        """Registers a decoder with this registry. Only one decoder can be
        registered for a type at a time.

        Decoder are responsible for keeping the input stream state clean: it
        should not read more than it has too.

        If a decoder is being registered for a type that is already associated
        with another decoder, an exception is raised unless the ``force``
        parameter is set to True: in that case, the new decoder replaces the
        old one.
        """
        try:
            decoder.set_decoder_registry(self)
        except AttributeError:
            pass

        for supported_type in decoder.supported_types:
            if supported_type in self.type_decoders and not force:
                raise Py4JError(
                    "This type, {0}, is already registered.".format(
                        supported_type))
            self.type_decoders[supported_type] = decoder

    def decode_response(self, input_stream, *args, **kwargs):
        """TODO
        """
        decoded_arguments = []
        while True:
            argument = self.decode_argument(input_stream, *args, **kwargs)
            if argument == END_DECODED_ARGUMENT:
                break
            else:
                decoded_arguments.append(argument)
        return decoded_arguments

    def decode_argument(
            self, input_stream, java_client=None, python_proxy_pool=None):
        """TODO
        """
        arg_type = unpack("!h", input_stream.read(2))[0]
        decoder = self.type_decoders.get(arg_type)
        if not decoder:
            raise Py4JProtocolError("Cannot decode {0}".format(arg_type))
        value = decoder.decode(
            input_stream, arg_type, java_client=java_client,
            python_proxy_pool=python_proxy_pool,
            string_encoding=self.string_encoding)
        return DecodedArgument(arg_type, value)


class EncoderRegistry(object):
    """Registry that holds all possible encoders used to encode Python
    arguments to Py4J arguments.

    This class is not thread-safe: if multiple thread tries to register
    encoders at the same time, concurrent modification errors may be raised.

    Multiple threads can call the encode methods though if they are not
    registering encoders at the same time.
    """

    def __init__(
            self, string_encoding=DEFAULT_STRING_ENCODING,
            id_mode=LONG_ID_MODE):
        self.type_encoders = defaultdict(list)
        self.all_encoders = deque()
        self.string_encoding = string_encoding
        self.id_mode = id_mode

    @classmethod
    def get_default_encoder_registry(
            cls, string_encoding=DEFAULT_STRING_ENCODING,
            id_mode=LONG_ID_MODE):
        """Returns an Encoder Registry with default encoders and ordering.
        Can be use as a basis to add other encoders.
        """
        registry = cls(string_encoding=string_encoding, id_mode=id_mode)
        for encoder_cls in DEFAULT_ENCODERS:
            registry.register_encoder(encoder_cls())
        for encoder_cls in DEFAULT_REFERENCE_ENCODERS[id_mode]:
            registry.register_encoder(encoder_cls())

        return registry

    def add_python_collection_encoders(self):
        """Adds converters that copies the elements of a Python collection into
        a Java collection. Both collections are not synchronized, i.e., a
        change on the Java side is not reflected on the Python side.
        """
        from py4j.java_collections import (
            PythonListEncoder, PythonMapEncoder, PythonSetEncoder)
        self.register_encoder(PythonListEncoder())
        self.register_encoder(PythonMapEncoder())
        self.register_encoder(PythonSetEncoder())

    def register_encoder(self, encoder):
        """Registers an encoder with this registry. The encoder can be
        associated with specific types to speed up encoding.

        When a Python argument is sent for encoding, if its type matches a
        type explicitly supported by a encoder, the registry will try these
        encoders first, in the order they were registered.

        If the specific type encoding did not work or if no encoders are
        registered for the type of the argument, the registry will try all
        encoders.

        Encoders that are registered to specific types are appended to the
        full list of encoders.

        Encoders that are not registered to specific types are prepended to
        the full list of encoders so they are always tried first when all
        encoders are considered.

        Specific types are great to optimize common-case scenarios, but they
        must also support inheritance (e.g., if a custom type inherits from a
        base type), hence their inclusion in the list of all encoders.
        """
        try:
            encoder.set_encoder_registry(self)
        except AttributeError:
            pass

        if encoder.supported_types:
            for supported_type in encoder.supported_types:
                self.type_encoders[supported_type].append(encoder)
            self.all_encoders.append(encoder)
        else:
            self.all_encoders.appendleft(encoder)

    def encode_command(self, command, *args, **kwargs):
        encoded_arguments = []
        encoded_arguments.append(self._encode_command(command))
        for argument in args:
            encoded_arguments.append(self.encode(argument, **kwargs))
        return encoded_arguments

    def encode_command_lazy(self, command, *args, **kwargs):
        yield self._encode_command(command)

        for argument in args:
            yield self.encode(argument, **kwargs)

    def _encode_command(self, command):
        return EncodedArgument(COMMAND_TYPE, None, pack("!h", command))

    def encode(
            self, argument, java_client=None, python_proxy_pool=None,
            force_type=None):
        if isinstance(argument, EncodedArgument):
            return argument

        if force_type:
            arg_type = force_type
        else:
            arg_type = type(argument)

        for encoder in self.type_encoders.get(arg_type, []):
            result = encoder.encode_specific(
                argument, arg_type,
                java_client=java_client,
                python_proxy_pool=python_proxy_pool,
                string_encoding=self.string_encoding)
            if result != CANNOT_ENCODE:
                return result

        for encoder in self.all_encoders:
            result = encoder.encode(
                argument, arg_type,
                java_client=java_client,
                python_proxy_pool=python_proxy_pool,
                string_encoding=self.string_encoding)
            if result != CANNOT_ENCODE:
                return result
        raise Py4JProtocolError(
            "Cannot encode argument {0} of type {1}".format(
                argument, arg_type))


class BaseEncoder(object):

    def encode(self, argument, arg_type, **options):
        if any((isinstance(argument, a_type) for
                a_type in self.supported_types)):
            return self.encode_specific(argument, arg_type)
        else:
            return CANNOT_ENCODE


class NoneEncoder(BaseEncoder):

    supported_types = SUPPORTED_NONE_TYPES

    def encode_specific(self, argument, arg_type, **options):
        return EncodedArgument(NULL_TYPE, None, None)


class IntEncoder(BaseEncoder):

    supported_types = SUPPORTED_INT_TYPES

    def encode_specific(self, argument, arg_type, **options):
        if argument <= JAVA_MAX_INT and argument >= JAVA_MIN_INT:
            return EncodedArgument(INTEGER_TYPE, None, pack("!i", argument))
        else:
            return EncodedArgument(LONG_TYPE, None, pack("!q", argument))


class DecimalEncoder(BaseEncoder):

    supported_types = [Decimal]

    def encode_specific(self, argument, arg_type, **options):
        value = bytestrrepr(argument)
        return EncodedArgument(DECIMAL_TYPE, len(value), value)


class BoolEncoder(BaseEncoder):

    supported_types = [bool]

    def encode_specific(self, argument, arg_type, **options):
        if argument:
            final_type = BOOLEAN_TRUE_TYPE
        else:
            final_type = BOOLEAN_FALSE_TYPE
        return EncodedArgument(final_type, None, None)


class DoubleEncoder(BaseEncoder):

    supported_types = [float]

    def encode_specific(self, argument, arg_type, **options):
        return EncodedArgument(DOUBLE_TYPE, None, pack("!d", argument))


class BytesEncoder(BaseEncoder):

    supported_types = SUPPORTED_BYTE_TYPES

    def encode_specific(self, argument, arg_type, **options):
        return EncodedArgument(BYTES_TYPE, len(argument), argument)


class StringEncoder(BaseEncoder):

    supported_types = SUPPORTED_STRING_TYPES

    def encode_specific(self, argument, arg_type, **options):
        string_encoding = options.get(
            "string_encoding", DEFAULT_STRING_ENCODING)
        value = get_encoded_string(argument, string_encoding)
        return EncodedArgument(STRING_TYPE, len(value), value)


class PythonProxyLongEncoder(object):

    supported_types = []

    def encode(self, argument, arg_type, **options):
        try:
            java_interfaces = ";".join(argument.Java.implements)
        except AttributeError:
            return CANNOT_ENCODE
        except TypeError:
            return CANNOT_ENCODE

        pool = options["python_proxy_pool"]
        proxy_id = pack("!q", pool.put(argument))
        string_encoding = options.get(
            "string_encoding", DEFAULT_STRING_ENCODING)
        java_interfaces_bytes = get_encoded_string(
            java_interfaces, string_encoding)
        value = proxy_id + java_interfaces_bytes
        return EncodedArgument(
            PYTHON_REFERENCE_LONG_TYPE, len(value), value)


class JavaObjectLongEncoder(object):

    supported_types = []

    def __init__(self):
        # Circular import! Still more logical to put this encoder here instead
        # of inside the java_gateway module.
        # TODO Push JavaObject to binary protocol, but keep implementation in
        # java_gateway?
        from py4j.java_gateway import JavaObject
        self.supported_types = [JavaObject]

    def encode_specific(self, argument, arg_type, **options):
        return self.encode_java_object(argument._get_object_id())

    @classmethod
    def encode_java_object(cls, object_id):
        return EncodedArgument(
            JAVA_REFERENCE_LONG_TYPE, None, pack("!q", object_id))

    def encode(self, argument, arg_type, **options):
        try:
            object_id = argument._get_object_id()
            return self.encode_java_object(object_id)
        except AttributeError:
            return CANNOT_ENCODE


class NoneDecoder(object):

    supported_types = [NULL_TYPE]

    def decode(self, input_stream, arg_type, **options):
        return None


class IntDecoder(object):

    supported_types = [INTEGER_TYPE, LONG_TYPE]

    def decode(self, input_stream, arg_type, **options):
        if arg_type == INTEGER_TYPE:
            return unpack("!i", input_stream.read(4))[0]
        else:
            return unpack("!q", input_stream.read(8))[0]


class DecimalDecoder(object):

    supported_types = [Decimal]

    def decode(self, input_stream, arg_type, **options):
        size = unpack(
            DEFAULT_SIZE_PACK_FORMAT,
            input_stream.read(DEFAULT_SIZE_BYTES_SIZE))[0]
        unicode_string = unicode(
            input_stream.read(size), DEFAULT_BYTESTRING_ENCODING)
        return Decimal(unicode_string)


class DoubleDecoder(object):

    supported_types = [DOUBLE_TYPE]

    def decode(self, input_stream, arg_type, *args, **kwargs):
        return unpack("!d", input_stream.read(8))[0]


class BoolDecoder(object):
    supported_types = [BOOLEAN_TRUE_TYPE, BOOLEAN_FALSE_TYPE]

    def decode(self, input_stream, arg_type, **options):
        return arg_type == BOOLEAN_TRUE_TYPE


class StringDecoder(object):
    supported_types = [STRING_TYPE]

    def decode(self, input_stream, arg_type, **options):
        string_encoding = options.get(
            "string_encoding", DEFAULT_STRING_ENCODING)

        size = unpack(
            DEFAULT_SIZE_PACK_FORMAT,
            input_stream.read(DEFAULT_SIZE_BYTES_SIZE))[0]

        unicode_string = unicode(input_stream.read(size), string_encoding)

        return unicode_string


class BytesDecoder(object):
    supported_types = [BYTES_TYPE]

    def decode(self, input_stream, arg_type, **options):
        size = unpack(
            DEFAULT_SIZE_PACK_FORMAT,
            input_stream.read(DEFAULT_SIZE_BYTES_SIZE))[0]

        return input_stream.read(size)


class PythonProxyLongDecoder(object):
    supported_types = [PYTHON_REFERENCE_LONG_TYPE]

    def decode(self, input_stream, arg_type, **options):
        proxy_id = unpack("!q", input_stream.read(8))[0]
        # Will raise an exception if it no longer exists
        return options["python_proxy_pool"][proxy_id]


class JavaObjectLongDecoder(object):
    supported_types = [JAVA_REFERENCE_LONG_TYPE]

    def __init__(self):
        from py4j.java_gateway import JavaObject
        self.JavaObject = JavaObject

    def decode(self, input_stream, arg_type, **options):
        object_id = unpack("!q", input_stream.read(8))[0]
        return self.JavaObject(object_id, options["java_client"])


def get_encoded_string(value, string_encoding):
    """Returns a bytestring from a string. The string can be unicode
    (Python 3's base string or Python 2's unicode) or a bytestring
    (Python 3's bytes or Python 2's str).

    If it is unicode, the string is encoded using string_encoding.
    """
    # If unicode, we need to encode
    if isinstance(value, unicode):
        value = value.encode(string_encoding)
    return value


def send_encoded_command(encoded_command, socket_instance):
    max_size = io.DEFAULT_BUFFER_SIZE
    buffer = bytearray()
    for arg in encoded_command:
        buffer.extend(pack("!h", arg.type))
        if arg.size:
            buffer.extend(pack(
                DEFAULT_SIZE_PACK_FORMAT, arg.size))
        if arg.value:
            if len(arg.value) > max_size:
                socket_instance.sendall(buffer)
                # clear() does not exist in python 2.x
                buffer = bytearray()
                socket_instance.sendall(arg.value)
                continue
            else:
                buffer.extend(arg.value)
        if len(buffer) > max_size:
            socket_instance.sendall(buffer)
            # clear() does not exist in python 2.x
            buffer = bytearray()

    if buffer:
        socket_instance.sendall(buffer)


DEFAULT_ENCODERS = (
    NoneEncoder,
    BoolEncoder,
    DecimalEncoder,
    IntEncoder,
    DoubleEncoder,
    BytesEncoder,
    StringEncoder,
)

DEFAULT_DECODERS = (
    NoneDecoder,
    BoolDecoder,
    IntDecoder,
    DecimalDecoder,
    DoubleDecoder,
    BytesDecoder,
    StringDecoder,
    JavaObjectLongDecoder,
    PythonProxyLongDecoder,
)


DEFAULT_REFERENCE_ENCODERS = {
    LONG_ID_MODE: (
        PythonProxyLongEncoder,
        JavaObjectLongEncoder,
    ),
    UUID_ID_MODE: (  # TODO
        PythonProxyLongEncoder,
        JavaObjectLongEncoder,
    )
}
