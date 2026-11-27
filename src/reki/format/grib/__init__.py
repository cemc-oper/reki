"""Protected ordinary GRIB imports backed by the ecCodes implementation."""
from reki.readers.grib.eccodes import load_message_from_file, load_messages_from_file
from reki.readers.grib import load_fields_from_file, fix_level_type


def load_field_from_file(file_path, parameter, level_type=None, level=None, engine="eccodes", **kwargs):
    from reki._legacy import check_engine
    from reki.readers.grib.eccodes import load_field_from_file as load_eccodes
    check_engine(engine)
    if isinstance(level_type, str):
        level_type = fix_level_type(level_type)
    return load_eccodes(file_path, parameter, level_type, level, **kwargs)


__all__ = ["load_field_from_file", "load_fields_from_file", "fix_level_type", "load_message_from_file", "load_messages_from_file"]
