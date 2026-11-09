"""Independent strict per-launch evidence validation, not a Python-free host claim."""
import ntpath

def normal(path, require):
    require(isinstance(path,str) and path and '\x00' not in path and ntpath.isabs(path)
        and bool(ntpath.splitdrive(path)[0]), 'Expected a fully qualified Windows image path.')
    return ntpath.normcase(ntpath.normpath(path))

def summary(data, require):
    require(data.get('launch_path_policy')=='windows-system-directories-only'
        and data.get('external_python_absence_claimed') is False
        and data.get('standalone_process_image_audit_required') is True
        and data.get('standalone_process_image_audit_passed') is True
        and data.get('installation_performed') is False,
        'Missing truthful standalone launch policy or successful process audit.')
    for key in ('external_python_removed_from_path','external_python_removed_from_child_path',
                'external_python_removed_from_tested_launch_path'):
        require(key not in data, 'Obsolete blanket Python-absence claim in final receipt.')

def record(row, exe_name, require):
    require(isinstance(row,dict), 'Missing launch receipt.')
    command=row.get('command')
    require(isinstance(command,list) and command and all(isinstance(x,str) for x in command), 'Missing actual EXE command.')
    image=normal(command[0],require)
    require(ntpath.basename(image)==ntpath.normcase(exe_name), 'Launch did not target the exact portable EXE name.')
    audit=row.get('process_image_audit')
    require(isinstance(audit,dict) and audit.get('required') is True and audit.get('passed') is True
        and audit.get('errors')==[], 'Launch process-image audit failed or missing.')
    images=audit.get('images')
    require(isinstance(images,list) and images and all(isinstance(i,dict) for i in images), 'No retained image observations.')
    require(type(audit.get('total_job_processes')) is int and type(audit.get('retained_process_handles')) is int
        and audit['total_job_processes']==audit['retained_process_handles']==len(images), 'Incomplete job process coverage.')
    require(all(type(i.get('pid')) is int and i['pid']>0 for i in images)
        and len({i['pid'] for i in images})==len(images), 'Missing or duplicate native process IDs.')
    require(all(normal(i.get('image'),require)==image for i in images), 'External process image differs from copied EXE.')

def launch_preflight(data, require):
    require(isinstance(data,dict) and type(data.get('schema_version')) is int and data['schema_version']==1
        and data.get('unsafe_path_entries')==[]
        and data.get('absolute_path_execution_blocked') is False
        and data.get('machine_python_absence_claimed') is False
        and data.get('process_execution_policy_enforced') is False,
            'Missing truthful host launch-environment disclosure.')
    paths=data.get('path_entries')
    require(isinstance(paths,list) and len(paths)==2, 'Unexpected launch PATH policy.')
    norm=[normal(path,require) for path in paths]
    require(norm[0]==ntpath.join(norm[1],'system32')
        and data.get('launch_path')==';'.join(paths), 'Launch PATH is not the two explicit Windows directories.')
    normal(data.get('controller_python'),require)
    require(isinstance(data.get('controller_python_version'),str) and data['controller_python_version']
        and isinstance(data.get('controller_which'),dict)
        and set(data['controller_which'])=={'python.exe','python3.exe','py.exe'}, 'Missing controller Python disclosure.')
    candidates=data.get('reachable_candidates')
    require(isinstance(candidates,list) and all(isinstance(i,dict) and i.get('origin') in {'launch_path','windows_implicit_search'}
        and i.get('name') in {'python.exe','python3.exe','py.exe'} and isinstance(i.get('path'),str) for i in candidates),
        'Missing native candidate scan.')
    require(data.get('path_and_implicit_directory_scan_passed') is (not candidates), 'Host presence scan contradicts its findings.')
