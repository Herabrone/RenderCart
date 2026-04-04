"""
Style presets for image generation.
Each preset defines a prompt template and inference parameters.
"""

from typing import Dict, Any

# Style presets mapping
STYLE_PRESETS = {
    "lifestyle": {
        "prompt_template": "{user_prompt}, professional lifestyle photography, natural lighting, realistic colors, outdoor setting, high quality, 8K",
        "inference_kwargs": {
            "steps": 30,
            "guidance_scale": 7.5,
            "strength": 0.7
        }
    },
    "studio": {
        "prompt_template": "{user_prompt}, professional studio photography, clean background, sharp focus, high resolution, product shot, 8K",
        "inference_kwargs": {
            "steps": 25,
            "guidance_scale": 8.0,
            "strength": 0.6
        }
    },
    "ad": {
        "prompt_template": "{user_prompt}, advertising campaign, vibrant colors, eye-catching composition, high contrast, professional grade, billboard ready, 8K",
        "inference_kwargs": {
            "steps": 35,
            "guidance_scale": 9.0,
            "strength": 0.8
        }
    }
}


def get_style_preset(style_name: str) -> Dict[str, Any]:
    """
    Get preset configuration for a given style.
    
    Args:
        style_name: Name of the style (lifestyle, studio, ad)
        
    Returns:
        Dictionary with prompt_template and inference_kwargs
        
    Raises:
        ValueError: If style is not found
    """
    if style_name not in STYLE_PRESETS:
        raise ValueError(f"Unknown style: {style_name}. Available styles: {list(STYLE_PRESETS.keys())}")
    
    return STYLE_PRESETS[style_name]


def apply_style_to_prompt(user_prompt: str, style_name: str) -> str:
    """
    Apply style preset to user prompt.
    
    Args:
        user_prompt: User's original prompt
        style_name: Name of the style preset
        
    Returns:
        Formatted prompt with style applied
    """
    preset = get_style_preset(style_name)
    return preset["prompt_template"].format(user_prompt=user_prompt)


def get_inference_params(style_name: str) -> Dict[str, Any]:
    """
    Get inference parameters for a given style.
    
    Args:
        style_name: Name of the style preset
        
    Returns:
        Dictionary with inference parameters (steps, guidance_scale, strength)
    """
    preset = get_style_preset(style_name)
    return preset["inference_kwargs"]