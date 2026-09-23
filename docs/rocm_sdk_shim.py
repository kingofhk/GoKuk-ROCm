"""Compatibility shim: rocm_sdk module expected by torch.

torch's _rocm_init.py calls::

    import rocm_sdk
    rocm_sdk.initialize_process(
        preload_shortnames=['amd_comgr', 'amdhip64', 'hiprtc', ...],
        check_version='7.12.0a20260311')

AMD used to ship a `rocm_sdk` Python package directly via the nightly
wheel index. Around mid-2026 AMD restructured the distribution so that:

- ``rocm_sdk_core``       : metadata + ``_dist_info.ALL_LIBRARIES`` registry
- ``_rocm_sdk_core``      : bin/, lib/, include/, share/ native content
- ``_rocm_sdk_libraries`` : bin/, .kpack/ ROCm runtime libraries
- ``rocm_sdk_device_gfx<arch>`` : per-GPU kpack + arch-specific DLLs

The new packages ship *native libraries only*. They do NOT provide a
Python wrapper that exposes ``initialize_process(preload_shortnames=...)``.

This shim adapts torch's expected API to the new layout. Drop it into
``site-packages/rocm_sdk.py`` next to ``torch`` and the install will
proceed past the ``import rocm_sdk`` line.

Resolution logic
-----------------

For each requested shortname, look up its ``LibraryEntry`` in
``rocm_sdk_core._dist_info``, then search for the matching DLL in:

1. The package's own bin/ directory
   (``_rocm_sdk_core/bin`` or ``_rocm_sdk_libraries/bin``)
2. The HIP SDK install directory (configured via ``ROCM_HOME`` or
   the well-known ``C:\\Program Files\\AMD\\ROCm\\<version>\\bin``)

Returned paths are added to ``os.add_dll_directory`` so torch's
``_load_dll_libraries`` step succeeds when it later tries to
``LoadLibrary`` each one.

Limitations
-----------

- Only resolves shortnames whose ``LibraryEntry.dll_pattern`` is set.
- Returns an empty list for shortnames whose packages are missing
  (e.g. ``miopen`` if MIOpen.dll is absent). The caller decides
  whether to abort or continue.
- Does NOT call ``LoadLibrary`` itself. That is torch's job.
"""