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

        cudaPkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            cudaSupport = true;
          };
        };
        cudaPy = cudaPkgs.python313;

        # Packages available under python3Packages.<name>
        # Quoted attrs are required for names containing hyphens.
        pythonDeps = ps:
          (with ps; [
            sounddevice
            evdev
            pynput
            tkinter
            numpy
            mypy
            pytest
            ruff
            setuptools
            build
            twine
          ])
          ++ [ ps."faster-whisper" ps."dbus-next" ];

        # Optional deps for the Wayland cursor-overlay feature (pyproject: cursor-overlay extra).
        # Requires system gtk4 + gtk4-layer-shell packages.
        cursorOverlayPythonDeps = ps: with ps; [ pygobject3 pycairo ];
        cursorOverlaySystemDeps = with pkgs; [ gtk4 gtk4-layer-shell ];

        # System-level CLI tools for text insertion and window detection
        systemDeps = with pkgs; [
          xclip
          xdotool
          xprop
          wl-clipboard
          ydotool
        ];

        voxy = py.pkgs.buildPythonApplication {
          pname = "voxy-linux";
          version = "0.1.0";
          src = ./.;
          format = "pyproject";

          nativeBuildInputs = with py.pkgs; [ setuptools ];
          propagatedBuildInputs = (pythonDeps py.pkgs) ++ systemDeps;
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

        devShells.cuda = cudaPkgs.mkShell {
          packages =
            [ (cudaPy.withPackages pythonDeps) ]
            ++ systemDeps;

          shellHook = ''
            echo "voxy cuda dev — $(python --version)"
          '';
        };

        devShells.cursor-overlay = pkgs.mkShell {
          packages =
            [ (py.withPackages (ps: pythonDeps ps ++ cursorOverlayPythonDeps ps)) ]
            ++ systemDeps
            ++ cursorOverlaySystemDeps;

          shellHook = ''
            echo "voxy cursor-overlay dev — $(python --version)"
          '';
        };
      }
    ))
    // {
      nixosModules.voxy = import ./nixos-module.nix { inherit self; };
    };
}
