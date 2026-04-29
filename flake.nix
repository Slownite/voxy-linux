{
  description = "voxy — local offline voice dictation for Linux";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        py = pkgs.python313;

        # Packages available under python3Packages.<name>
        # faster-whisper uses quoted attr due to hyphen in name.
        pythonDeps = ps:
          (with ps; [
            sounddevice
            evdev
            pynput
            tkinter
            numpy
            mypy
            pytest
            setuptools
            build
          ])
          ++ [ ps."faster-whisper" ];

        # System-level CLI tools for text insertion
        systemDeps = with pkgs; [
          xclip
          xdotool
          wl-clipboard
          ydotool
        ];

        voxy = py.pkgs.buildPythonApplication {
          pname = "voxy-linux";
          version = "0.1.0";
          src = ./.;
          format = "pyproject";

          nativeBuildInputs = with py.pkgs; [ setuptools ];
          propagatedBuildInputs = pythonDeps py.pkgs;
        };
      in
      {
        packages.default = voxy;

        devShells.default = pkgs.mkShell {
          packages =
            [ (py.withPackages pythonDeps) ]
            ++ systemDeps;

          shellHook = ''
            echo "voxy dev — $(python --version)"
          '';
        };
      }
    ))
    // {
      nixosModules.voxy = import ./nixos-module.nix { inherit self; };
    };
}
