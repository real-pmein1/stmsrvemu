"""
===============================================================================
 PKG Neutering Integration Helper
===============================================================================

This module provides integration helpers for the optimized neutering system,
allowing seamless switching between original and optimized neutering, and
enabling dual WAN/LAN generation when both caches are needed.

Usage in clientupdateserver.py:
    from utilities.neuter_integration import smart_neuter

    # Instead of:
    # neuter(pkg_in, pkg_out, server_ip, port, islan)

    # Use:
    # smart_neuter(pkg_in, cache_base, filename, server_ip, public_ip, port, islan)
===============================================================================
"""

import os
import logging
from typing import Tuple, Optional
from config import get_config

log = logging.getLogger("neuter_integration")
config = get_config()

# Configuration flag to enable/disable optimized neutering
USE_OPTIMIZED_NEUTERING = True


def smart_neuter(pkg_in: str, cache_base: str, filename: str,
                 server_ip: str, public_ip: str, server_port: str,
                 is_lan: bool, is_beta: bool = False) -> str:
    """
    Smart neutering that automatically uses dual generation when beneficial.

    This function checks if both LAN and WAN caches are missing and generates
    both in a single pass if so. Otherwise, it generates just the requested one.

    Args:
        pkg_in: Path to source PKG file
        cache_base: Base cache directory (e.g., "files/cache")
        filename: PKG filename (e.g., "Steam_45.pkg")
        server_ip: Server LAN IP
        public_ip: Server public/WAN IP
        server_port: Directory server port
        is_lan: True if requesting LAN version
        is_beta: True if this is a beta package

    Returns:
        Path to the cached PKG file to serve
    """
    # Determine output paths
    if public_ip != "0.0.0.0":
        # Dual mode: separate internal/external caches
        if is_beta:
            lan_path = os.path.join(cache_base, "internal", "betav2", filename)
            wan_path = os.path.join(cache_base, "external", "betav2", filename)
        else:
            lan_path = os.path.join(cache_base, "internal", filename)
            wan_path = os.path.join(cache_base, "external", filename)
    else:
        # Single mode: only LAN cache
        if is_beta:
            lan_path = os.path.join(cache_base, "betav2", filename)
        else:
            lan_path = os.path.join(cache_base, filename)
        wan_path = None

    # Determine which file we need to serve
    requested_path = lan_path if is_lan else (wan_path or lan_path)

    # If requested file exists, return it
    if os.path.isfile(requested_path):
        return requested_path

    # Need to generate - check if we should use dual generation
    if USE_OPTIMIZED_NEUTERING and wan_path is not None:
        # Check if both are missing
        lan_missing = not os.path.isfile(lan_path)
        wan_missing = not os.path.isfile(wan_path)

        if lan_missing and wan_missing:
            # Both missing - use dual generation for efficiency
            log.info(f"Both LAN and WAN caches missing, using dual neutering for {filename}")
            _ensure_directories(lan_path, wan_path)

            try:
                from utilities.neuter_optimized import neuter_dual
                neuter_dual(pkg_in, lan_path, wan_path, server_ip, public_ip, server_port)
                return requested_path
            except Exception as e:
                log.error(f"Optimized dual neutering failed: {e}, falling back to original")
                # Fall through to single generation

        elif lan_missing or wan_missing:
            # Only one missing - use single generation
            missing_path = lan_path if lan_missing else wan_path
            missing_is_lan = lan_missing
            log.info(f"Single cache missing, generating {missing_path}")
            _ensure_directories(missing_path)

            try:
                if USE_OPTIMIZED_NEUTERING:
                    from utilities.neuter_optimized import neuter_single
                    neuter_single(pkg_in, missing_path, server_ip, server_port, missing_is_lan)
                else:
                    from utilities.neuter import neuter
                    ip = server_ip if missing_is_lan else public_ip
                    neuter(pkg_in, missing_path, ip, server_port, missing_is_lan)
                return requested_path
            except Exception as e:
                log.error(f"Neutering failed: {e}")
                raise

    # Single mode or fallback
    _ensure_directories(requested_path)

    try:
        if USE_OPTIMIZED_NEUTERING:
            from utilities.neuter_optimized import neuter_single
            neuter_single(pkg_in, requested_path, server_ip, server_port, is_lan)
        else:
            from utilities.neuter import neuter
            ip = server_ip if is_lan else public_ip
            neuter(pkg_in, requested_path, ip, server_port, is_lan)
    except Exception as e:
        log.error(f"Neutering failed: {e}")
        raise

    return requested_path


def check_and_generate_both(pkg_in: str, lan_out: str, wan_out: str,
                            server_ip: str, public_ip: str,
                            server_port: str) -> Tuple[bool, bool]:
    """
    Check if LAN/WAN caches exist and generate missing ones efficiently.

    If both are missing, uses dual generation. If only one is missing,
    generates just that one. If both exist, does nothing.

    Args:
        pkg_in: Source PKG path
        lan_out: LAN cache output path
        wan_out: WAN cache output path
        server_ip: Server LAN IP
        public_ip: Server public IP
        server_port: Directory server port

    Returns:
        Tuple of (lan_generated, wan_generated)
    """
    lan_exists = os.path.isfile(lan_out)
    wan_exists = os.path.isfile(wan_out)

    if lan_exists and wan_exists:
        return False, False

    if not lan_exists and not wan_exists:
        # Both missing - use dual generation
        _ensure_directories(lan_out, wan_out)

        if USE_OPTIMIZED_NEUTERING:
            from utilities.neuter_optimized import neuter_dual
            neuter_dual(pkg_in, lan_out, wan_out, server_ip, public_ip, server_port)
        else:
            # Fallback: generate both separately
            from utilities.neuter import neuter
            neuter(pkg_in, lan_out, server_ip, server_port, True)
            neuter(pkg_in, wan_out, public_ip, server_port, False)

        return True, True

    # Only one missing
    if not lan_exists:
        _ensure_directories(lan_out)
        if USE_OPTIMIZED_NEUTERING:
            from utilities.neuter_optimized import neuter_single
            neuter_single(pkg_in, lan_out, server_ip, server_port, True)
        else:
            from utilities.neuter import neuter
            neuter(pkg_in, lan_out, server_ip, server_port, True)
        return True, False

    if not wan_exists:
        _ensure_directories(wan_out)
        if USE_OPTIMIZED_NEUTERING:
            from utilities.neuter_optimized import neuter_single
            neuter_single(pkg_in, wan_out, server_ip, server_port, False)
        else:
            from utilities.neuter import neuter
            neuter(pkg_in, wan_out, public_ip, server_port, False)
        return False, True

    return False, False


def pregenerate_pkg_caches(pkg_dir: str, cache_base: str,
                           server_ip: str, public_ip: str,
                           server_port: str, is_beta: bool = False) -> dict:
    """
    Pre-generate all PKG caches for faster first-request response.

    This can be called during server startup to pre-populate caches.

    Args:
        pkg_dir: Directory containing source PKG files
        cache_base: Base cache directory
        server_ip: Server LAN IP
        public_ip: Server public IP
        server_port: Directory server port
        is_beta: True for beta packages

    Returns:
        Dict with counts: {'generated': N, 'skipped': N, 'errors': N}
    """
    result = {'generated': 0, 'skipped': 0, 'errors': 0}

    if not os.path.isdir(pkg_dir):
        log.warning(f"PKG directory not found: {pkg_dir}")
        return result

    # Find all PKG files
    pkg_files = [f for f in os.listdir(pkg_dir) if f.endswith('.pkg')]

    for pkg_file in pkg_files:
        pkg_path = os.path.join(pkg_dir, pkg_file)

        if public_ip != "0.0.0.0":
            if is_beta:
                lan_out = os.path.join(cache_base, "internal", "betav2", pkg_file)
                wan_out = os.path.join(cache_base, "external", "betav2", pkg_file)
            else:
                lan_out = os.path.join(cache_base, "internal", pkg_file)
                wan_out = os.path.join(cache_base, "external", pkg_file)

            try:
                lan_gen, wan_gen = check_and_generate_both(
                    pkg_path, lan_out, wan_out, server_ip, public_ip, server_port
                )
                if lan_gen or wan_gen:
                    result['generated'] += 1
                else:
                    result['skipped'] += 1
            except Exception as e:
                log.error(f"Failed to pre-generate {pkg_file}: {e}")
                result['errors'] += 1
        else:
            if is_beta:
                out_path = os.path.join(cache_base, "betav2", pkg_file)
            else:
                out_path = os.path.join(cache_base, pkg_file)

            if os.path.isfile(out_path):
                result['skipped'] += 1
                continue

            try:
                _ensure_directories(out_path)
                if USE_OPTIMIZED_NEUTERING:
                    from utilities.neuter_optimized import neuter_single
                    neuter_single(pkg_path, out_path, server_ip, server_port, True)
                else:
                    from utilities.neuter import neuter
                    neuter(pkg_path, out_path, server_ip, server_port, True)
                result['generated'] += 1
            except Exception as e:
                log.error(f"Failed to pre-generate {pkg_file}: {e}")
                result['errors'] += 1

    log.info(f"Pre-generation complete: {result['generated']} generated, "
             f"{result['skipped']} skipped, {result['errors']} errors")
    return result


def _ensure_directories(*paths):
    """Ensure parent directories exist for given file paths."""
    for path in paths:
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)


# =============================================================================
# BENCHMARKING UTILITIES
# =============================================================================

def benchmark_neutering(pkg_path: str, iterations: int = 3) -> dict:
    """
    Benchmark original vs optimized neutering performance.

    Args:
        pkg_path: Path to a PKG file to use for testing
        iterations: Number of iterations for averaging

    Returns:
        Dict with timing results
    """
    import time
    import tempfile
    import shutil

    results = {
        'original_single': [],
        'optimized_single': [],
        'optimized_dual': [],
    }

    server_ip = config.get("server_ip", "127.0.0.1")
    public_ip = config.get("public_ip", "0.0.0.0")
    server_port = config.get("dir_server_port", "27030")

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(iterations):
            # Benchmark original single
            out_path = os.path.join(tmpdir, f"orig_{i}.pkg")
            start = time.perf_counter()
            from utilities.neuter import neuter
            neuter(pkg_path, out_path, server_ip, server_port, True)
            results['original_single'].append(time.perf_counter() - start)

            # Benchmark optimized single
            out_path = os.path.join(tmpdir, f"opt_single_{i}.pkg")
            start = time.perf_counter()
            from utilities.neuter_optimized import neuter_single
            neuter_single(pkg_path, out_path, server_ip, server_port, True)
            results['optimized_single'].append(time.perf_counter() - start)

            # Benchmark optimized dual
            lan_out = os.path.join(tmpdir, f"opt_lan_{i}.pkg")
            wan_out = os.path.join(tmpdir, f"opt_wan_{i}.pkg")
            start = time.perf_counter()
            from utilities.neuter_optimized import neuter_dual
            neuter_dual(pkg_path, lan_out, wan_out, server_ip, public_ip, server_port)
            results['optimized_dual'].append(time.perf_counter() - start)

    # Calculate averages
    summary = {
        'original_single_avg': sum(results['original_single']) / iterations,
        'optimized_single_avg': sum(results['optimized_single']) / iterations,
        'optimized_dual_avg': sum(results['optimized_dual']) / iterations,
    }

    # Calculate improvements
    summary['single_improvement'] = (
        (summary['original_single_avg'] - summary['optimized_single_avg']) /
        summary['original_single_avg'] * 100
    )
    summary['dual_vs_2x_original'] = (
        (2 * summary['original_single_avg'] - summary['optimized_dual_avg']) /
        (2 * summary['original_single_avg']) * 100
    )

    log.info(f"Benchmark results:")
    log.info(f"  Original single: {summary['original_single_avg']:.3f}s")
    log.info(f"  Optimized single: {summary['optimized_single_avg']:.3f}s "
             f"({summary['single_improvement']:.1f}% faster)")
    log.info(f"  Optimized dual: {summary['optimized_dual_avg']:.3f}s "
             f"({summary['dual_vs_2x_original']:.1f}% faster than 2x original)")

    return summary
