"""
Common testing utilities

"""
import io


def build_ini(values):
    output = io.BytesIO()
    for section in values:
        output.write('[{}]\n'.format(section).encode('utf-8'))
        for key in values[section]:
            output.write('{0}={1}\n'.format(
                key, values[section][key]).encode('utf-8'))
    output.seek(0)
    return output.read()
