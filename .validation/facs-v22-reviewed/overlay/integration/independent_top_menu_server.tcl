# Independent display-free Tk menu command server. Real Tcl and tkinter.Menu.
# Widget model only: this is explicitly not a native Tk/Aqua rendering backend.
namespace eval audit { variable widgets {}; variable writes {}; variable default_tearoff 1 }
proc menu {path args} {
    set options [dict merge [dict create -tearoff $::audit::default_tearoff] $args]
    set rows {}
    if {[dict get $options -tearoff]} { lappend rows [dict create kind tearoff] }
    dict set ::audit::widgets $path [dict create options $options rows $rows]
    interp alias {} $path {} audit::dispatch $path
    return $path
}
proc winfo {op path} {
    if {$op ne "exists"} { error "Unsupported winfo operation $op" }
    return [expr {$path eq "." || [dict exists $::audit::widgets $path]}]
}
proc destroy {path} {
    foreach key [dict keys $::audit::widgets] {
        if {$key eq $path || [string first "$path." $key] == 0} {
            dict unset ::audit::widgets $key
            rename $key {}
        }
    }
}
proc audit::dispatch {path op args} {
    variable widgets; variable writes
    set rows [dict get $widgets $path rows]
    switch -- $op {
        add - insert {
            if {$op eq "insert"} {set at [lindex $args 0]; set args [lrange $args 1 end]} else {set at end}
            set kind [lindex $args 0]
            set row [dict merge [dict create kind $kind -label {} -menu {} -accelerator {} -underline -1 -state normal] [lrange $args 1 end]]
            set rows [linsert $rows $at $row]
        }
        delete {
            set first [lindex $args 0]; set last [lindex $args 1]
            if {$last eq ""} {set last $first}
            if {$last eq "end"} {set last [expr {[llength $rows]-1}]}
            set rows [lreplace $rows $first $last]
        }
        index {
            set at [lindex $args 0]
            if {$at eq "end"} {return [expr {[llength $rows] ? [llength $rows]-1 : "none"}]}
            return $at
        }
        type {return [dict get [lindex $rows [lindex $args 0]] kind]}
        entrycget {return [format %s [dict get [lindex $rows [lindex $args 0]] [lindex $args 1]]]}
        entryconfigure {
            set at [lindex $args 0]
            set options [lrange $args 1 end]
            if {[llength $options] == 0} {
                set configs {}
                dict for {key value} [lindex $rows $at] {
                    if {[string index $key 0] eq "-"} { lappend configs [list $key {} {} {} $value] }
                }
                return $configs
            }
            lappend writes [list $path $at $options]
            set rows [lreplace $rows $at $at [dict merge [lindex $rows $at] $options]]
        }
        invoke {
            if {[dict get [lindex $rows [lindex $args 0]] -state] eq "disabled"} {return {}}
            set callback [dict get [lindex $rows [lindex $args 0]] -command]
            if {$callback ne ""} {return [uplevel #0 $callback]}
            return {}
        }
        cget {return [dict get $widgets $path options [lindex $args 0]]}
        default {error "Unsupported menu command: $path $op $args"}
    }
    dict set widgets $path rows $rows
    return {}
}
