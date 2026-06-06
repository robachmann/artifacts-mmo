import importlib
import pkgutil


# Auto-import all modules inside the actions package except internal files
def load_all_action_modules():
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        name = module_info.name
        if name.endswith('_action'):
            importlib.import_module(f'{package}.{name}')
