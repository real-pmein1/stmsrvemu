import os
def normalize_path(base_path, *path_components):
    """
    Combine a base path with an arbitrary number of path components and return
    the normalized absolute path.

    Parameters:
    - base_path (str): The initial path (relative or absolute).
    - *path_components (str): Additional path components to append.

    Returns:
    - str: The normalized absolute path.
    """
    # Combine the base path with all additional path components
    combined_path = os.path.join(base_path, *path_components)

    # Normalize the path to eliminate redundant separators and up-level references
    normalized_path = os.path.normpath(combined_path)

    # Convert the normalized path to an absolute path
    absolute_path = os.path.abspath(normalized_path)

    return absolute_path
