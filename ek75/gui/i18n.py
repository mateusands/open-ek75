# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""UI strings, in English and Brazilian Portuguese.

The rest of the project is English (CLAUDE.md), and so is the default here.
Portuguese is included because the keyboard's official software is sold in
Brazil in Portuguese, and picked automatically when the system locale asks for
it — set OPEN_EK75_LANG=en or =pt to override.
"""
import os

from ..core import settings

STRINGS = {
    "en": {
        "app_title": "open-ek75",
        "brightness_note": "LED_CMD_BRIGHTNESS · 0-255 on the wire",
        "speed_slow": "Slow",
        "speed_normal": "Normal",
        "speed_fast": "Fast",
        "no_direction": "This effect has no direction",
        "no_speed": "This effect has no speed",
        "from_windows_app": "from the official Windows app",
        "direction_inert": "stored by the firmware, but this model shows no\nvisible change — see PROTOCOL.md",
        "device_subtitle": "Dareu TK51G family — sold as Husky HTG200/HTG500/HTG800 V2",
        "backup_blurb": ("The keyboard keeps its lighting AND its key map in\n"
                          "persistent memory: both survive unplugging the cable.\n"
                          "A backup saves the two together and is the way back\n"
                          "from a change you do not like."),
        "layout_note": ("The layout below is read from Dareu's own device profile "
                         "— 83 keys, the vendor's own geometry."),
        "todo_connection": "Wired/wireless connection toggle",
        "todo_profiles": "Profile selector",
        "todo_sleep": "Sleep timer — changing it",
        "nav_home": "Device",
        "nav_keys": "Keys",
        "nav_lighting": "Lighting",
        "nav_macros": "Macros",
        "backlight": "Backlight",
        "side_light": "Side light",
        "region_n": "Region {n}",
        "advanced": "Advanced options",
        "brightness": "Brightness",
        "speed": "Speed",
        "direction": "Direction",
        "color": "Colour",
        "pick_color": "Pick a colour…",
        "rgb_mode": "RGB (the keyboard picks)",
        "color_rgb_only": "This effect is RGB only — the firmware picks its\ncolours and ignores any you send.",
        "fn_guide": "Fn shortcuts",
        "fn_needs_device": ("Connect the keyboard to read its shortcuts.\n"
                             "They are not listed from the vendor profile: on the unit\n"
                             "this was built against, 23 of its assignments disagree\n"
                             "with the hardware. See PROTOCOL.md."),
        "fn_reading": "Reading the key map…",
        "keys_live": "Read from the keyboard",
        "keys_base": "Base",
        "keys_fn": "Fn",
        "keys_click": "Click a key to see what it is assigned to.",
        "fn_guide_hint": ("Read from the keyboard itself, not from the vendor's\n"
                           "profile. None of this is printed on the case."),
        "fn_search": "Filter",
        "color_ignored": "This zone ignores the colour for this effect —\nit renders a fixed pattern. See PROTOCOL.md.",
        "apply": "Apply",
        "apply_live": "Apply as I change",
        "turn_off": "Turn off",
        "backup": "Back up",
        "restore": "Restore",
        "connected": "Connected — {path}",
        "disconnected": "Keyboard not found",
        "searching": "Looking for the keyboard…",
        "reading": "Reading the keyboard…",
        "applied": "Applied to region {region}",
        "apply_failed": "The keyboard did not confirm that command",
        "backup_saved": "Backed up to {path}",
        "backup_failed": "Backup failed: {error}",
        "restored": "Restored from {path}",
        "keys_blurb": ("What each key does, read from the keyboard itself — the "
                        "vendor's\nprofile disagrees with this hardware on 23 "
                        "assignments. Click a key to\nsee it, then assign it "
                        "something else."),
        "keys_assign": "Assign",
        "keys_layer": "Layer",
        "keys_source": "Assign to",
        "keys_source_key": "A key",
        "keys_source_media": "Media",
        "keys_source_copy": "Copy",
        "keys_pick_target": "Pick what this key should do.",
        "keys_chosen": "Chosen: {name}",
        "keys_apply": "Apply",
        "keys_revert": "Revert to backup",
        "keys_working": "Writing…",
        "keys_writing": "Writing the assignment and reading it back…",
        "keys_written": "The keyboard now reports: {name}",
        "keys_refused": "The keyboard did not acknowledge the write — nothing changed.",
        "keys_locked": ("This key cannot be remapped: it is half of Fn+Esc, the "
                         "factory reset built into the firmware. That is the way "
                         "back from a bad key write, and it must keep working."),
        "keys_need_backup": ("No key map has been backed up yet. Take a backup "
                              "from the Device page first — nothing here writes "
                              "without a way back."),
        "keys_no_hatch": ("Warning: this keyboard did not report an Fn modifier "
                           "or a factory reset, so the Fn+Esc way back was not "
                           "found on it. Keep your backup."),
        "keys_hatch": ("The way back: Revert uses your backup. Under that, "
                        "Fn+Esc is a factory reset built into the firmware — it "
                        "needs nothing from this software."),
        "keys_no_targets": ("Nothing to copy: this keyboard reports no "
                             "assignment from the vetted list. Resets, pairing "
                             "and the knob are deliberately not copyable."),
        "backup_unreadable": "{name} is not a backup this can read ({detail}).",
        "restoring": "Restoring the lighting…",
        "restoring_keys": "Restoring the lighting and the key map — the key map "
                          "is 166 writes and takes about 17 seconds.",
        "restore_partial": "Restored with failures: {regions} lighting "
                           "region(s), {keys} key assignment(s). The backup is "
                           "still on disk — running restore again is the fix.",
        "profiles_active": "{listed}   (active: {active})",
        "profiles_only_one": "— the vendor app's other slots must be created first",
        "no_backup": "No backup file yet — use Back up first",
        "auto_backup": "Saved a backup of this keyboard to {path}",
        "device_model": "Model",
        "device_pid": "USB id",
        "device_node": "HID node",
        "device_firmware": "Firmware in the vendor profile",
        "device_battery": "Battery",
        "device_sleep": "Sleep timer",
        "sleep_disabled": "disabled",
        "sleep_minutes": "{minutes} min",
        "battery_reading": "reading…",
        "battery_unknown": "unknown",
        "device_profiles": "Profiles",
        "device_regions": "Lighting regions",
        "yes": "yes",
        "no": "no",
        "region_source": "found via {source}",
        "not_implemented": "Not implemented yet",
        "preview_note": "Preview is approximate — the keyboard renders the real effect.",
        "unconfirmed": "unconfirmed on hardware",
        "permission_short": "No permission to open the keyboard's HID node",
        "permission_title": "Device permission",
        "permission_hint": (
            "The keyboard's HID node is root-only on this system.\n\n"
            "Install the udev rule once, then replug the keyboard:\n"
            "    sudo sh packaging/install.sh"
        ),
        "macros_todo": (
            "Macros need CLASS_MACRO, which is not ported yet.\n\n"
            "MacroCreate / SetMacroData / GetMacroIdList exist in\n"
            "docs/vendor-reference/tgdevice.js and use the same multi-packet\n"
            "transfer this project already implements for the region list."
        ),
        "effects": {
            # The official software's English labels, from LangLib.dll
            # (themes/en.baml), with two deliberate departures: its CamelCase
            # run-ons are spaced out ("SteadyStream" -> "Steady stream") and its
            # two typos are not reproduced here ("StrartUp", "StreamingFream"),
            # since an English reader has no reason to want either. Effect 10 is
            # `Rotate` on the wire and "Diffusion" to the user — that one is the
            # vendor's own naming and is kept.
            "Off": "Off",
            "Static": "Static",
            "Breathing": "Breathing",
            "Neon": "Neon",
            "Reactive": "Reactive",
            "Wave": "Wave",
            "Raindrop": "Raindrop",
            "Gather": "Gather",
            "Ripple": "Ripple",
            "RunningLight": "Running light",
            "Rotate": "Diffusion",
            "Starlit": "Starlit",
            "Heatup": "Heat up",
            "CustomFrame1": "Custom 1", "CustomFrame2": "Custom 2",
            "CustomFrame3": "Custom 3", "CustomFrame4": "Custom 4",
            "CustomFrame5": "Custom 5",
            "StreamingFrame": "Streaming frame",
            "Lap": "Lap",
            "RainbowW": "Rainbow",
            "LightWave": "Light wave",
            "SteadyStream": "Steady stream",
            "StartUp": "Start up",
            "AreaReactive": "Area reactive",
            "LineReactive": "Line reactive",
            "Waterfall": "Waterfall",
            "Scanning": "Scanning",
            "Heartbeat": "Heartbeat",
            "Fluxay": "Flux",
            "HeartBreath": "Heart breath",
            "MoonBreath": "Moon breath",
            "StarBreath": "Star breath",
        },
    },
    "pt": {
        "app_title": "open-ek75",
        "brightness_note": "LED_CMD_BRIGHTNESS · 0-255 no fio",
        "speed_slow": "Lento",
        "speed_normal": "Normal",
        "speed_fast": "Rápido",
        "no_direction": "Este efeito não tem direção",
        "no_speed": "Este efeito não tem velocidade",
        "from_windows_app": "do app oficial da Husky",
        "direction_inert": "o firmware guarda o byte, mas este modelo não\nmuda visivelmente — veja PROTOCOL.md",
        "device_subtitle": "Família Dareu TK51G — vendido como Husky HTG200/HTG500/HTG800 V2",
        "backup_blurb": ("O teclado guarda a iluminação E o mapa de teclas em\n"
                          "memória persistente: os dois sobrevivem a desconectar\n"
                          "o cabo. O backup salva os dois juntos e é o caminho\n"
                          "de volta de uma mudança que não agradou."),
        "layout_note": ("O layout abaixo vem do perfil de dispositivo da própria "
                         "Dareu — 83 teclas, a geometria do fabricante."),
        "todo_connection": "Alternar conexão com fio / sem fio",
        "todo_profiles": "Seletor de perfis",
        "todo_sleep": "Tempo de espera — alterar",
        "nav_home": "Dispositivo",
        "nav_keys": "Teclas",
        "nav_lighting": "Iluminação",
        "nav_macros": "Macros",
        "backlight": "Luz de fundo",
        "side_light": "Luz lateral",
        "region_n": "Região {n}",
        "advanced": "Opções avançadas",
        "brightness": "Brilho",
        "speed": "Velocidade",
        "direction": "Direção",
        "color": "Cor",
        "pick_color": "Escolher cor…",
        "rgb_mode": "RGB (o teclado escolhe)",
        "color_rgb_only": "Este efeito é só RGB — o firmware escolhe as cores\ne ignora qualquer uma que você envie.",
        "fn_guide": "Atalhos com Fn",
        "fn_needs_device": ("Conecte o teclado para ler os atalhos dele.\n"
                             "Eles não são listados a partir do perfil do fabricante:\n"
                             "na unidade em que isto foi construído, 23 atribuições dele\n"
                             "discordam do hardware. Veja o PROTOCOL.md."),
        "fn_reading": "Lendo o mapa de teclas…",
        "keys_live": "Lido do teclado",
        "keys_base": "Base",
        "keys_fn": "Fn",
        "keys_click": "Clique numa tecla para ver a atribuição dela.",
        "fn_guide_hint": ("Lidos do próprio teclado, não do perfil do fabricante.\n"
                           "Nada disso vem impresso no case."),
        "fn_search": "Filtrar",
        "color_ignored": "Esta zona ignora a cor neste efeito — ela mostra\num padrão fixo. Veja PROTOCOL.md.",
        "apply": "Aplicar",
        "apply_live": "Aplicar enquanto altero",
        "turn_off": "Desligar",
        "backup": "Backup",
        "restore": "Restaurar",
        "connected": "Conectado — {path}",
        "disconnected": "Teclado não encontrado",
        "searching": "Procurando o teclado…",
        "reading": "Lendo o teclado…",
        "applied": "Aplicado na região {region}",
        "apply_failed": "O teclado não confirmou esse comando",
        "backup_saved": "Backup salvo em {path}",
        "backup_failed": "Falha no backup: {error}",
        "restored": "Restaurado de {path}",
        "keys_blurb": ("O que cada tecla faz, lido do próprio teclado — o perfil "
                        "do\nfabricante discorda deste hardware em 23 atribuições. "
                        "Clique numa tecla\npara ver, e então atribua outra coisa "
                        "a ela."),
        "keys_assign": "Atribuir",
        "keys_layer": "Camada",
        "keys_source": "Atribuir a",
        "keys_source_key": "Uma tecla",
        "keys_source_media": "Mídia",
        "keys_source_copy": "Copiar",
        "keys_pick_target": "Escolha o que esta tecla deve fazer.",
        "keys_chosen": "Escolhido: {name}",
        "keys_apply": "Aplicar",
        "keys_revert": "Voltar ao backup",
        "keys_working": "Gravando…",
        "keys_writing": "Gravando a atribuição e lendo de volta…",
        "keys_written": "O teclado agora reporta: {name}",
        "keys_refused": "O teclado não confirmou a escrita — nada mudou.",
        "keys_locked": ("Esta tecla não pode ser remapeada: ela é metade do "
                         "Fn+Esc, o reset de fábrica embutido no firmware. Esse é "
                         "o caminho de volta de uma escrita ruim, e precisa "
                         "continuar funcionando."),
        "keys_need_backup": ("Nenhum mapa de teclas foi salvo ainda. Faça um "
                              "backup na página Dispositivo primeiro — nada aqui "
                              "escreve sem caminho de volta."),
        "keys_no_hatch": ("Atenção: este teclado não reportou um modificador Fn "
                           "nem um reset de fábrica, então o caminho de volta "
                           "Fn+Esc não foi encontrado nele. Guarde seu backup."),
        "keys_hatch": ("O caminho de volta: Voltar ao backup usa o seu arquivo. "
                        "Abaixo disso, Fn+Esc é um reset de fábrica embutido no "
                        "firmware — não depende deste software."),
        "keys_no_targets": ("Nada para copiar: este teclado não reporta nenhuma "
                             "atribuição da lista permitida. Resets, pareamento "
                             "e o knob não são copiáveis de propósito."),
        "backup_unreadable": "{name} não é um backup que dê para ler ({detail}).",
        "restoring": "Restaurando a iluminação…",
        "restoring_keys": "Restaurando a iluminação e o mapa de teclas — são 166 "
                          "escritas e leva cerca de 17 segundos.",
        "restore_partial": "Restaurado com falhas: {regions} região(ões) de "
                           "iluminação, {keys} atribuição(ões) de tecla. O backup "
                           "continua no disco — repetir o restore resolve.",
        "profiles_active": "{listed}   (ativo: {active})",
        "profiles_only_one": "— os outros slots do app do fabricante precisam ser criados",
        "no_backup": "Ainda não há backup — use Backup primeiro",
        "auto_backup": "Backup deste teclado salvo em {path}",
        "device_model": "Modelo",
        "device_pid": "ID USB",
        "device_node": "Nó HID",
        "device_firmware": "Firmware no perfil do fabricante",
        "device_battery": "Bateria",
        "device_sleep": "Tempo de espera",
        "sleep_disabled": "desativado",
        "sleep_minutes": "{minutes} min",
        "battery_reading": "lendo…",
        "battery_unknown": "desconhecido",
        "device_profiles": "Perfis",
        "device_regions": "Regiões de iluminação",
        "yes": "sim",
        "no": "não",
        "region_source": "descobertas via {source}",
        "not_implemented": "Ainda não implementado",
        "preview_note": "A prévia é aproximada — o efeito real é renderizado pelo teclado.",
        "unconfirmed": "não confirmado no hardware",
        "permission_short": "Sem permissão para abrir o nó HID do teclado",
        "permission_title": "Permissão de acesso",
        "permission_hint": (
            "O nó HID do teclado é acessível só por root neste sistema.\n\n"
            "Instale a regra udev uma vez e replugue o teclado:\n"
            "    sudo sh packaging/install.sh"
        ),
        "macros_todo": (
            "Macros dependem de CLASS_MACRO, ainda não portada.\n\n"
            "MacroCreate / SetMacroData / GetMacroIdList existem em\n"
            "docs/vendor-reference/tgdevice.js e usam a mesma transferência\n"
            "multi-pacote que este projeto já implementa para a lista de regiões."
        ),
        "effects": {
            # Verbatim from the official software's Brazilian Portuguese string
            # table (LangLib.dll, themes/ptbr.baml), in TG_LIGHT_EFFECT_INDEX
            # order. Taken from the vendor rather than translated here, so the
            # names match what a user of the Husky software already knows —
            # including the ones it leaves in English ("RunningLight") and its
            # own spelling ("Arco Iris", unaccented).
            "Off": "Desligado",
            "Static": "Estático",
            "Breathing": "Respiração",
            "Neon": "Néon",
            "Reactive": "Reativo",
            "Wave": "Onda",
            "Raindrop": "Gota de chuva",
            "Gather": "Reunir",
            "Ripple": "Ondulação",
            "RunningLight": "RunningLight",
            "Rotate": "Difusão",
            "Starlit": "Iluminado por Estrelas",
            "Heatup": "Aquecimento",
            "CustomFrame1": "Custom1", "CustomFrame2": "Custom2",
            "CustomFrame3": "Custom3", "CustomFrame4": "Custom4",
            "CustomFrame5": "Custom5",
            "StreamingFrame": "StreamingFream",
            "Lap": "Volta",
            "RainbowW": "Arco Iris",
            "LightWave": "Onda de Luz",
            "SteadyStream": "Fluxo Estável",
            "StartUp": "Inicialização",
            "AreaReactive": "Reativa por Área",
            "LineReactive": "Reativa por Linha",
            "Waterfall": "Cascata",
            "Scanning": "Escaneamento",
            "Heartbeat": "Batimento Cardíaco",
            "Fluxay": "Fluxo",
            "HeartBreath": "Respiração do Coração",
            "MoonBreath": "Respiração da Lua",
            "StarBreath": "Respiração das Estrelas",
        },
    },
}


def _detect():
    """The language to start in.

    English by default, deliberately: this is a public tool and English is the
    project's own language (README, CLI, PROTOCOL.md). Portuguese is one click
    away in the UI and the choice is remembered. `OPEN_EK75_LANG` overrides
    both, which is what the tests and screenshots use.
    """
    override = os.environ.get("OPEN_EK75_LANG", "").strip().lower()[:2]
    if override in STRINGS:
        return override
    stored = settings.load().get("language", "en")
    return stored if stored in STRINGS else "en"


LANG = _detect()


def available():
    """(code, label) for every language, in the order the switch shows them."""
    return (("en", "EN"), ("pt", "PT-BR"))


def set_language(code):
    """Switch language and remember it. Returns True if anything changed.

    Callers must rebuild their widgets afterwards: every string is read once,
    when a widget is built.
    """
    global LANG
    if code not in STRINGS or code == LANG:
        return False
    LANG = code
    settings.update(language=code)
    return True


def t(key, **kwargs):
    text = STRINGS[LANG].get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def effect_label(english_name):
    """A localised effect name, falling back to the vendor driver's own name.

    Untranslated effects deliberately show the driver's English identifier
    rather than an invented translation, so what you see matches what
    PROTOCOL.md calls it.
    """
    return STRINGS[LANG].get("effects", {}).get(english_name, english_name)
