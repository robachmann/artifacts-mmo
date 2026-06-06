import importlib
import pkgutil


# Auto-import all modules inside the templates package except internal files
def load_all_template_modules():
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        name = module_info.name
        if name.endswith('_template'):
            importlib.import_module(f'{package}.{name}')
