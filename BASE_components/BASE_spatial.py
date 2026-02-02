"""
Shared spatial partitioning logic for optimized collision detection.
Used by both client (prediction) and server (authoritative logic).
"""

class SpatialGrid:
    """
    Optimized spatial partitioning for collision detection.
    Divides the world into a grid of cells to reduce collision checks.
    """
    def __init__(self, cell_size=250):
        self.cell_size = cell_size
        self.grid = {}  # (cell_x, cell_y) -> [objects]

    def clear(self):
        self.grid.clear()

    def add(self, obj):
        """Add an object to all cells it overlaps."""
        # Determine boundaries - handles various object types
        min_x, max_x, min_y, max_y = 0, 0, 0, 0
        found_bounds = False

        if hasattr(obj, 'world_center') and hasattr(obj, 'size'):
            # Circle/Square with world_center and size
            cx, cy = obj.world_center
            half_size = obj.size / 2
            min_x, max_x = cx - half_size, cx + half_size
            min_y, max_y = cy - half_size, cy + half_size
            found_bounds = True
        elif hasattr(obj, 'world_center') and hasattr(obj, 'radius'):
            # Circle with world_center and radius (GrassField)
            cx, cy = obj.world_center
            r = obj.radius
            min_x, max_x = cx - r, cx + r
            min_y, max_y = cy - r, cy + r
            found_bounds = True
        elif hasattr(obj, 'location') and hasattr(obj, 'radius'):
            # Circle with location and radius
            cx, cy = obj.location
            r = obj.radius
            min_x, max_x = cx - r, cx + r
            min_y, max_y = cy - r, cy + r
            found_bounds = True
        elif hasattr(obj, 'location') and hasattr(obj, 'size'):
            # Square with location and size
            cx, cy = obj.location
            half_size = obj.size / 2
            min_x, max_x = cx - half_size, cx + half_size
            min_y, max_y = cy - half_size, cy + half_size
            found_bounds = True
        elif hasattr(obj, 'rect'):
            min_x, max_x = obj.rect.left, obj.rect.right
            min_y, max_y = obj.rect.top, obj.rect.bottom
            found_bounds = True
        elif hasattr(obj, 'float_x') and hasattr(obj, 'width'):
            min_x, max_x = obj.float_x, obj.float_x + obj.width
            min_y, max_y = obj.float_y, obj.float_y + obj.height
            found_bounds = True
        
        if not found_bounds:
            # Fallback for generic objects with location but no size
            loc = getattr(obj, 'location', getattr(obj, 'world_center', None))
            if loc:
                min_x = max_x = loc[0]
                min_y = max_y = loc[1]
            else:
                return

        # Calculate cell range
        start_col = int(min_x // self.cell_size)
        end_col = int(max_x // self.cell_size)
        start_row = int(min_y // self.cell_size)
        end_row = int(max_y // self.cell_size)

        for col in range(start_col, end_col + 1):
            for row in range(start_row, end_row + 1):
                cell_key = (col, row)
                if cell_key not in self.grid:
                    self.grid[cell_key] = []
                self.grid[cell_key].append(obj)

    def get_nearby(self, x, y, radius, filter_func=None):
        """
        Get objects in cells overlapping a circle.
        Optional filter_func(obj) -> bool can be provided.
        """
        min_x, max_x = x - radius, x + radius
        min_y, max_y = y - radius, y + radius

        start_col = int(min_x // self.cell_size)
        end_col = int(max_x // self.cell_size)
        start_row = int(min_y // self.cell_size)
        end_row = int(max_y // self.cell_size)

        nearby = set()
        for col in range(start_col, end_col + 1):
            for row in range(start_row, end_row + 1):
                cell_key = (col, row)
                if cell_key in self.grid:
                    for obj in self.grid[cell_key]:
                        if filter_func is None or filter_func(obj):
                            nearby.add(obj)
        return nearby

    def get_closest(self, x, y, radius, filter_func=None):
        """
        Find the single closest object within radius that matches filter_func.
        Returns (object, distance) or (None, infinity).
        """
        nearby = self.get_nearby(x, y, radius, filter_func)
        closest_obj = None
        min_dist_sq = float('inf')

        import math
        for obj in nearby:
            # Get object center
            ox, oy = 0, 0
            found_center = False
            
            if hasattr(obj, 'world_center'):
                ox, oy = obj.world_center
                found_center = True
            elif hasattr(obj, 'location'):
                ox, oy = obj.location
                found_center = True
            elif hasattr(obj, 'rect'):
                ox, oy = obj.rect.centerx, obj.rect.centery
                found_center = True
            elif hasattr(obj, 'float_x'):
                ox = obj.float_x + getattr(obj, 'width', 0) / 2
                oy = obj.float_y + getattr(obj, 'height', 0) / 2
                found_center = True
            
            if not found_center:
                continue

            dist_sq = (x - ox)**2 + (y - oy)**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_obj = obj

        if closest_obj:
            return closest_obj, math.sqrt(min_dist_sq)
        return None, float('inf')
