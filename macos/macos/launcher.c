/* Universal macOS entry point. All runtime files stay inside this app. */
typedef unsigned int uint32_t;
typedef unsigned long size_t;
extern int _NSGetExecutablePath(char *, uint32_t *);
extern char *realpath(const char *, char *);
extern char *strrchr(const char *, int);
extern int snprintf(char *, size_t, const char *, ...);
extern int setenv(const char *, const char *, int);
extern int unsetenv(const char *);
extern int dprintf(int, const char *, ...);
extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);

int main(int argc, char **argv) {
    char executable[16384], resolved[16384], main_path[16384], script[16384];
    char framework[16384], library[16384];
    uint32_t length = sizeof(executable);
    if (_NSGetExecutablePath(executable, &length) || !realpath(executable, resolved)) {
        dprintf(2, "Facility Studio: cannot resolve application path.\n");
        return 70;
    }
    if (snprintf(main_path, sizeof(main_path), "%s", resolved) >= (int)sizeof(main_path)) return 70;
    char *last = strrchr(resolved, '/');
    if (!last) return 70;
    *last = 0;
    if (snprintf(script, sizeof(script), "%s/../Resources/bootstrap.py", resolved) >= (int)sizeof(script)
        || snprintf(framework, sizeof(framework), "%s/../Frameworks/Python.framework/Versions/3.13", resolved) >= (int)sizeof(framework)
        || snprintf(library, sizeof(library), "%s/Python", framework) >= (int)sizeof(library)) {
        return 70;
    }
    /* Own the interpreter search path; never load a user's Python packages. */
    unsetenv("PYTHONPATH");
    unsetenv("PYTHONSTARTUP");
    unsetenv("PYTHONUSERBASE");
    unsetenv("PYTHONEXECUTABLE");
    unsetenv("__PYVENV_LAUNCHER__");
    unsetenv("PYTHONPLATLIBDIR");
    unsetenv("PYTHONINSPECT");
    unsetenv("PYTHONOPTIMIZE");
    unsetenv("PYTHONVERBOSE");
    if (setenv("PYTHONHOME", framework, 1)
        || setenv("PYTHONNOUSERSITE", "1", 1)
        || setenv("PYTHONDONTWRITEBYTECODE", "1", 1)
        || setenv("PYTHONUTF8", "1", 1)) return 70;
    /* -s excludes user site packages; bootstrap also verifies all search paths. */
    char *arguments[argc + 5];
    arguments[0] = main_path;
    arguments[1] = "-s";
    arguments[2] = "-B";
    arguments[3] = script;
    for (int i = 1; i < argc; i++) arguments[i + 3] = argv[i];
    arguments[argc + 3] = 0;
    /* Embed CPython in the app's own main process, keeping the correct macOS
       main bundle, Dock icon, application menu and Cocoa main thread. */
    void *python = dlopen(library, 2 | 8); /* RTLD_NOW | RTLD_GLOBAL on macOS. */
    if (!python) {
        dprintf(2, "Facility Studio: cannot load bundled Python: %s\n", dlerror());
        return 71;
    }
    int (*python_main)(int, char **) = (int (*)(int, char **))dlsym(python, "Py_BytesMain");
    if (!python_main) {
        dprintf(2, "Facility Studio: Py_BytesMain is unavailable.\n");
        return 71;
    }
    return python_main(argc + 3, arguments);
}
