from google.protobuf import json_format

from .transport_pb2 import RawField


def convert_to_json(raw_field):
    return json_format.MessageToJson(raw_field)


def load_from_json(json_string, cls):
    return json_format.Parse(json_string, cls())
