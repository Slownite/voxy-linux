from voxy.config import PostProcessingConfig
from voxy.postprocess import PostProcessor

def test_empty_string() -> None:
    config = PostProcessingConfig()
    pp = PostProcessor(config)
    assert pp.process("") == ""

def test_auto_capitalize() -> None:
    config = PostProcessingConfig(auto_capitalize=True, punctuation_commands=False, strip_fillers=False)
    pp = PostProcessor(config)
    assert pp.process("hello world") == "Hello world"
    assert pp.process(" already capitalized") == "Already capitalized"

def test_punctuation_commands() -> None:
    config = PostProcessingConfig(punctuation_commands=True, auto_capitalize=False, strip_fillers=False)
    pp = PostProcessor(config)
    assert pp.process("hello comma world") == "hello, world"
    assert pp.process("stop period new paragraph start") == "stop.\n\nstart"

def test_strip_fillers() -> None:
    config = PostProcessingConfig(strip_fillers=True, auto_capitalize=False, punctuation_commands=False, fillers=("uh", "um"))
    pp = PostProcessor(config)
    assert pp.process("hello uh world um") == "hello world"

def test_custom_substitutions() -> None:
    config = PostProcessingConfig(
        punctuation_commands=True, 
        auto_capitalize=False, 
        strip_fillers=False,
        substitutions={"custom word": "replacement"}
    )
    pp = PostProcessor(config)
    assert pp.process("this is a custom word test") == "this is a replacement test"

def test_combined() -> None:
    config = PostProcessingConfig(
        punctuation_commands=True, 
        auto_capitalize=True, 
        strip_fillers=True,
        fillers=("uh",),
        substitutions={"comma": ","}
    )
    pp = PostProcessor(config)
    assert pp.process("uh hello comma world") == "Hello, world"
