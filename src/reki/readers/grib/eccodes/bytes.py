"""Native byte/message conversions with explicit transfer of handle ownership."""
import eccodes
from cedarkit_query import SourceError
from reki._legacy import reader_errors
from .message import load_message_from_file


def load_bytes_from_file(file_path, parameter=None, level_type=None, level=None, **kwargs):
    """Return unchanged bytes of the first matching message, releasing its handle."""
    message = load_message_from_file(file_path, parameter, level_type, level, **kwargs)
    if message is None:
        return None
    try:
        with reader_errors(file_path, "load_bytes_from_file"):
            return eccodes.codes_get_message(message)
    finally:
        eccodes.codes_release(message)


def create_message_from_bytes(raw_message):
    """Transfer the first decoded handle to the caller; empty bytes return None."""
    if not raw_message:
        return None
    with reader_errors("<bytes>", "create_message_from_bytes"):
        message = eccodes.codes_new_from_message(raw_message)
        if message is None:
            raise SourceError("decode_failed", "/message", "Bytes do not contain a GRIB message")
        return message


def create_messages_from_bytes(raw_message):
    """Transfer all handles in physical order; release partial results on failure."""
    messages = []
    try:
        while raw_message:
            message = create_message_from_bytes(raw_message)
            messages.append(message)
            size = eccodes.codes_get_message_size(message)
            if size <= 0 or size > len(raw_message):
                raise SourceError("decode_failed", "/message", "Truncated GRIB bytes")
            raw_message = raw_message[size:]
        return messages
    except BaseException:
        for message in messages:
            eccodes.codes_release(message)
        raise
