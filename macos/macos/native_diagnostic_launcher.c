/* External diagnostic embedding entry. Never writes or re-signs the App.
 * Uses its original CPython dylib and home; argv[0] is the original launcher
 * so Python-side path/signature checks continue to target the signed App.
 * The actual process/Cocoa main-bundle remains this external helper.
 */
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char app[PATH_MAX], script[PATH_MAX], helper[PATH_MAX];
    char home[PATH_MAX], library[PATH_MAX], original[PATH_MAX];
    if (argc < 3) {
        fprintf(stderr, "Usage: FacilityStudioProbe APP DIAGNOSTIC_SCRIPT [arguments...]\n");
        return 64;
    }
    if (!realpath(argv[1], app) || !realpath(argv[2], script)
        || !realpath(argv[0], helper)) {
        perror("FacilityStudioProbe: cannot resolve diagnostic paths");
        return 66;
    }
    if (snprintf(home, sizeof(home), "%s/Contents/Frameworks/Python.framework/Versions/3.13", app) >= (int)sizeof(home)
        || snprintf(library, sizeof(library), "%s/Python", home) >= (int)sizeof(library)
        || snprintf(original, sizeof(original), "%s/Contents/MacOS/FacilityStudio", app) >= (int)sizeof(original)) {
        fprintf(stderr, "FacilityStudioProbe: path too long\n");
        return 66;
    }
    if (access(library, R_OK) || access(original, X_OK) || access(script, R_OK)) {
        perror("FacilityStudioProbe: original runtime or diagnostic script missing");
        return 66;
    }
    const char *clear[] = {"PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE",
        "PYTHONEXECUTABLE", "__PYVENV_LAUNCHER__", "PYTHONPLATLIBDIR",
        "PYTHONINSPECT", "PYTHONOPTIMIZE", "PYTHONVERBOSE", NULL};
    for (int index = 0; clear[index]; index++) unsetenv(clear[index]);
    if (setenv("PYTHONHOME", home, 1)
        || setenv("PYTHONNOUSERSITE", "1", 1)
        || setenv("PYTHONDONTWRITEBYTECODE", "1", 1)
        || setenv("PYTHONUTF8", "1", 1)
        || setenv("PYTHONEXECUTABLE", original, 1)
        || setenv("FACILITY_PROBE_HELPER_EXECUTABLE", helper, 1)
        || setenv("FACILITY_PROBE_ORIGINAL_LAUNCHER", original, 1)) {
        perror("FacilityStudioProbe: cannot set runtime identity");
        return 70;
    }
    void *python = dlopen(library, RTLD_NOW | RTLD_GLOBAL);
    if (!python) {
        fprintf(stderr, "FacilityStudioProbe: cannot load original CPython: %s\n", dlerror());
        return 71;
    }
    int (*python_main)(int, char **) = (int (*)(int, char **))dlsym(python, "Py_BytesMain");
    if (!python_main) {
        fprintf(stderr, "FacilityStudioProbe: original CPython lacks Py_BytesMain\n");
        return 71;
    }
    char **arguments = calloc((size_t)argc + 2, sizeof(char *));
    if (!arguments) return 70;
    arguments[0] = original;
    arguments[1] = "-s";
    arguments[2] = "-B";
    arguments[3] = script;
    for (int index = 3; index < argc; index++) arguments[index + 1] = argv[index];
    int code = python_main(argc + 1, arguments);
    free(arguments);
    return code;
}
