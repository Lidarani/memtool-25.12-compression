# Copyright 2019-2023, 2025 NXP
"""TODO:summary line."""
import logging


class Singleton(type):
    """Singleton metaclass."""

    _instances = {}  # type: ignore

    def __call__(cls, *args, **kwargs):  # type: ignore
        """TODO:summary line."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class FactoryClass:
    """Generic factory class.

    Intended to be subclassed and used with RegistryMeta as metaclass
    """
    # Keep track of instances

    # TODO: see if registry should be  defined here as the PyCharm refractory suggested
    # registry = None
    instance_cache = {}  # type: ignore
    logger = logging.getLogger(__name__)

    class RegistryMeta(type):
        """Meta class to automatically register all subclasses derived from a given base class."""

        def __init__(cls, name, bases, dct):  # type: ignore
            """TODO:summary line."""
            if not hasattr(cls, 'registry'):
                # Create an empty registry if not present (ie this is the base class)
                cls.registry = {}
            else:
                # Store the class to the registry (this is a derived class)
                interface_id = name.lower()
                cls.registry[interface_id] = cls

            super(FactoryClass.RegistryMeta, cls).__init__(name, bases, dct)

    @classmethod
    def make_instance(cls, *args):  # type: ignore
        """Factory method which selects an actual subclass based on matches() class method.

        @return: new instance that matches args
        @raise RuntimeError: no subclass for args
        """
        # Identify the appropriate class from the registered subclasses
        candidates = [c for c in cls.registry.values() if c.matches(args)]
        if not candidates:
            msg = f'No matching {cls} subclass found to instantiate!'
            FactoryClass.logger.critical(msg)
            raise RuntimeError(msg)
        if len(candidates) > 1:
            msg = f'Multiple matching {cls} subclasses found to instantiate: {candidates}!'
            FactoryClass.logger.warning(msg)
        sub_cls = next(iter(candidates))

        # Return the new instance
        return sub_cls(*args)

    @classmethod
    def make_unique_instance(cls, *args):  # type: ignore
        """Factory method which selects an actual subclass based on matches() class method.

        Keeps track of instances and instantiates a new one only if the arguments differ
        @return: instance that matches key from args
        """
        # generate key
        parts = [cls.__name__]
        for arg in args:
            if isinstance(arg, dict):
                # treat dictionaries specially: keep ordered entries
                parts.append('_'.join(f'{k}:{v}' for k, v in sorted(arg.items())))
            else:
                parts.append(repr(arg))

        key = '_'.join(parts)
        hash_key = hash(key)
        if hash_key not in FactoryClass.instance_cache:
            inst = cls.make_instance(*args)
            FactoryClass.instance_cache[hash_key] = inst

        return FactoryClass.instance_cache[hash_key]

    @classmethod
    def make_unique_instance_without_caching(cls, *args):  # type: ignore
        """Factory method which selects an actual subclass based on matches() class method.

        Keeps track of instances and instantiates a new one only if the arguments differ
        @return: instance that matches key from args
        """
        # generate key
        parts = [cls.__name__]
        for arg in args:
            if isinstance(arg, dict):
                # treat dictionaries specially: keep ordered entries
                parts.append('_'.join(f'{k}:{v}' for k, v in sorted(arg.items())))
            else:
                parts.append(repr(arg))

        inst = cls.make_instance(*args)
        return inst

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Selection criterion - to be overridden in subclasses."""
        return False


class AppInterfaceFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """AppInterface class abstracts away potential differences in the way applications are built (symbol names etc)."""


class BackendFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """A Backend class provides a common interface to the underlying backend used to communicate to the target."""


class ProcessorFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """A Processor class provides a common interface to the underlying data used to load app to the target."""


class SDPFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """A SDP class provides a common interface to the SDP communication channel."""


class SDPSFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """A SDPS class provides a common interface to the SDP communication channel."""


class MBootFactory(FactoryClass, metaclass=FactoryClass.RegistryMeta):
    """A MBoot class provides a common interface to the MBoot communication channel."""
