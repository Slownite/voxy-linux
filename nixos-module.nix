{ self }:
{ config, lib, pkgs, ... }:

let
  cfg = config.services.voxy;

  configToml = ''
    [hotkey]
    key = "${cfg.hotkey}"

    [model]
    size = "${cfg.modelSize}"

    [insertion]
    method = "auto"

    [post_processing]
    punctuation_commands = true
    auto_capitalize = true
    strip_fillers = false
    fillers = ["uh", "um", "hmm"]

    [post_processing.substitutions]
    "new line" = "\n"
    "new paragraph" = "\n\n"
    "comma" = ","
    "period" = "."
    "question mark" = "?"
    "exclamation mark" = "!"
    "colon" = ":"
    "semicolon" = ";"

    [ui]
    overlay = true
    overlay_corner = "${cfg.overlayCorner}"
    audio_feedback = false

    [logging]
    level = "info"
  '';

  configFile = pkgs.writeText "voxy-config.toml" configToml;

  voxyPkg = self.packages.${pkgs.system}.default;
in
{
  options.services.voxy = {
    enable = lib.mkEnableOption "voxy local offline voice dictation";

    hotkey = lib.mkOption {
      type = lib.types.str;
      default = "right_alt";
      description = ''
        Key to hold for push-to-talk. Uses evdev/pynput key names.
        The user running voxy must be in the <literal>input</literal> group.
      '';
    };

    modelSize = lib.mkOption {
      type = lib.types.enum [
        "tiny" "tiny.en" "base" "base.en" "small" "small.en"
        "medium" "medium.en" "large-v1" "large-v2" "large-v3"
      ];
      default = "small";
      description = ''
        Whisper model size. Larger models produce more accurate transcriptions
        but require more RAM and CPU time. <literal>small</literal> is a good
        default for most hardware.
      '';
    };

    overlayCorner = lib.mkOption {
      type = lib.types.enum [ "top-left" "top-right" "bottom-left" "bottom-right" ];
      default = "bottom-right";
      description = "Screen corner where the recording overlay appears.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ voxyPkg ];

    systemd.user.services.voxy = {
      description = "voxy — local offline voice dictation for Linux";
      wantedBy = [ "graphical-session.target" ];
      partOf   = [ "graphical-session.target" ];
      after    = [ "graphical-session.target" ];
      environment = {
        VOXY_CONFIG = "${configFile}";
      };
      serviceConfig = {
        Type = "simple";
        ExecStart = "${voxyPkg}/bin/voxy";
        Restart = "on-failure";
      };
    };
  };
}
