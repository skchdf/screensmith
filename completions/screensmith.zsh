#compdef screensmith
# zsh completion for screensmith

_screensmith_outputs() {
    local -a outputs
    outputs=(${(f)"$(command -v kscreen-doctor >/dev/null 2>&1 && \
        kscreen-doctor -o 2>/dev/null | sed -n 's/^Output: [0-9]* \([^ ]*\).*/\1/p')"})
    _describe -t outputs 'output' outputs
}

_screensmith() {
    local -a commands
    commands=(
        'status:one-screen summary of the current setup'
        'outputs:list displays KWin knows about'
        'doctor:diagnose scaling problems'
        'scale:per-display scale factor'
        'xwayland:global multiplier for X11 apps'
        'rounding:QT_SCALE_FACTOR_ROUNDING_POLICY'
        'font-dpi:QT_FONT_DPI, the base size Qt assumes'
        'preset:apply a named bundle of settings'
        'backup:snapshot the config files screensmith touches'
        'restore:restore a snapshot'
    )

    _arguments -C \
        '--json[emit machine-readable JSON]' \
        '1: :->command' \
        '2: :->action' \
        '*:: :->rest'

    case $state in
        command) _describe -t commands 'screensmith command' commands ;;
        action)
            case $words[1] in
                scale)
                    _values 'scale action' get set reset
                    ;;
                xwayland|font-dpi|rounding)
                    _values 'action' get set reset
                    ;;
                preset)
                    _values 'preset' compact balanced hi-dpi
                    ;;
            esac
            ;;
        rest)
            case "$words[1]:$words[2]" in
                scale:set)
                    _arguments '--offline[write the config file, do not talk to KWin]' \
                        '1:output:_screensmith_outputs' \
                        '2:scale factor:'
                    ;;
                scale:get|scale:reset)
                    _arguments '1:output:_screensmith_outputs'
                    ;;
                rounding:set)
                    _values 'policy' PassThrough Round Ceil Floor
                    ;;
                restore)
                    _files -/
                    ;;
            esac
            ;;
    esac
}

_screensmith "$@"
