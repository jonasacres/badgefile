import json
import traceback
import os
import sys
from .log_target import LogTarget

class Console(LogTarget):
  def log_msg(self, info):
    severity_colorized = info["severity_str_short"]
    timestamp_colorized = info["timestamp_str"]
    src_reference_colorized = info["src_reference_short"]
    run_id_colorized = info['run_id']
    msg_colorized = info["msg"]

    color_not_banned = os.environ.get("NO_COLOR") is None
    color_supported_by_term = os.environ.get("TERM") in ["xterm-256color", "xterm-color", "xterm", "screen", "screen-256color", "screen-color", "xterm-kitty"]
    is_tty = sys.stdout.isatty()
    color_enabled = color_not_banned and color_supported_by_term and is_tty

    # Color codes
    RED        = "\033[31m"
    GREEN      = "\033[32m"
    YELLOW     = "\033[33m"
    BLUE       = "\033[34m"
    MAGENTA    = "\033[35m"
    CYAN       = "\033[36m"
    LIGHT_GRAY = "\033[90m"
    DARK_GRAY  = "\033[2m"  # Using dim/faint effect instead of dark gray
    RESET      = "\033[0m"

    # Map severity levels to colors
    SEVERITY_COLORS = {
        "FATAL":    MAGENTA,
        "CRITICAL": RED,
        "ERROR":    RED, 
        "WARN":     YELLOW,
        "NOTICE":   GREEN,
        "INFO":     None,
        "DEBUG":    LIGHT_GRAY,
        "TRACE":    DARK_GRAY,
    }

    if color_enabled:
      timestamp_colorized = f"{CYAN}{info['timestamp_str']}{RESET}"
      src_reference_colorized = f"{GREEN}{info['src_reference_short']}{RESET}"
      run_id_colorized = f"{YELLOW}{info['run_id']}{RESET}"

      color = SEVERITY_COLORS[info["severity_str"]]
      severity_colorized = f"{color}{info['severity_str_short']}{RESET}" if color else info['severity_str_short']
      msg_colorized = f"{color}{info['msg']}{RESET}" if color else info['msg']
    
    print("[%s] %s %s %30s -- %s" % (
           severity_colorized,
           run_id_colorized,
           timestamp_colorized,
           src_reference_colorized,
           msg_colorized))
    
    if info["exception"] is not None:
      exc = info["exception"]
      if color_enabled:
        print(f"{RED}Exception {exc.__class__.__name__}: {str(exc)}{RESET}")
      else:
        print(f"Exception {exc.__class__.__name__}: {str(exc)}")
      print(''.join(traceback.format_tb(exc.__traceback__)))

    if info["data"] is not None:
      if color_enabled:
        print(f"{BLUE}{json.dumps(info['data'], indent=2)}{RESET}")
      else:
        print(json.dumps(info["data"], indent=2))
      
