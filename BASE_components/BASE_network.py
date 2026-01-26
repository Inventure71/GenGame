import uuid
import pickle
import importlib

class NetworkObject:
    """
    Mixin class that provides network serialization capabilities for game objects.
    Handles identity generation and data/lightweight serialization for network transmission.
    """

    def __init__(self):
        # Generate unique network identity
        self.network_id = str(uuid.uuid4())

        # Flag to determine if graphics should be initialized
        self._graphics_initialized = False

        # Automatically detect the actual class and module (not the base class)
        actual_class = self.__class__
        self.module_path = actual_class.__module__
        self.class_name = actual_class.__name__

    def _set_network_identity(self, module_path: str, class_name: str):
        """Set the module and class information for network instantiation."""
        self.module_path = module_path
        self.class_name = class_name

    def init_graphics(self):
        """
        Initialize graphics resources (images, rects, sounds, etc.).
        Override in subclasses to load visual/sound assets.
        This method should be safe to call multiple times.
        """
        self._graphics_initialized = True

    def __getstate__(self):
        """
        Serialize object for network transmission.
        Returns only lightweight data, excluding heavy graphics resources.
        """
        state = self.__dict__.copy()

        # Remove heavy graphics resources and client-side-only visual state that shouldn't be transmitted
        heavy_keys = [
            'image', 'rect', 'mask', 'screen', 'font', 'sounds', 'sound',
            'surface', 'texture', 'sprite', 'animation_frames', 'particle_effects',
            '_graphics_initialized',
            # Client-side animation state (purely visual, doesn't affect gameplay)
            'animation_frame', 'animation_timer', 'animation_frame_count',
            '_prev_location'  # Client-side movement tracking
        ]

        for key in heavy_keys:
            state.pop(key, None)

        return state

    def __setstate__(self, state):
        """
        Deserialize object from network transmission.
        Restores data and reinitializes graphics locally.
        """
        self.__dict__.update(state)

        # Reinitialize graphics on the receiving end
        if hasattr(self, 'init_graphics'):
            self.init_graphics()

    @classmethod
    def create_from_network_data(cls, network_data: dict):
        """
        Factory method to create an object instance from network data.
        Dynamically imports and instantiates the correct class.

        Args:
            network_data: Dictionary containing serialized object data

        Returns:
            Instantiated object with restored data and graphics
        """
        try:
            # Extract module and class info
            module_path = network_data.get('module_path', '')
            class_name = network_data.get('class_name', '')

            if not module_path or not class_name:
                raise ValueError(f"Missing module_path or class_name in network data")

            # Dynamically import the module
            module = importlib.import_module(module_path)

            # Get the class
            obj_class = getattr(module, class_name)

            # Create instance without calling __init__ to avoid double initialization
            instance = obj_class.__new__(obj_class)

            # Restore the state
            instance.__setstate__(network_data)

            return instance

        except Exception as e:
            print(f"Error creating object from network data: {e}")
            return None