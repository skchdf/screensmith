# bash completion for screensmith
# Install: source this file, or copy it to /etc/bash_completion.d/screensmith

_screensmith() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="status outputs doctor scale xwayland rounding font-dpi preset backup restore"

    # Options that take a value.
    case "$prev" in
        scale)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "--offline" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "get set reset" -- "$cur") )
            fi
            return
            ;;
        xwayland|font-dpi)
            COMPREPLY=( $(compgen -W "get set reset" -- "$cur") )
            return
            ;;
        rounding)
            if [[ ${COMP_WORDS[COMP_CWORD-2]} == "set" ]]; then
                COMPREPLY=( $(compgen -W "PassThrough Round Ceil Floor" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "get set reset" -- "$cur") )
            fi
            return
            ;;
        preset)
            COMPREPLY=( $(compgen -W "compact balanced hi-dpi" -- "$cur") )
            return
            ;;
        restore)
            COMPREPLY=( $(compgen -W "--yes" -- "$cur") \
                        $(compgen -d -- "$cur") )
            return
            ;;
    esac

    # Output names, from the running session, if we can reach it.
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "--json --help" -- "$cur") )
        return
    fi

    local outputs
    outputs=$(command -v kscreen-doctor >/dev/null 2>&1 && \
              kscreen-doctor -o 2>/dev/null | sed -n 's/^Output: [0-9]* \([^ ]*\).*/\1/p')
    COMPREPLY=( $(compgen -W "$commands $outputs" -- "$cur") )
}
complete -F _screensmith screensmith
