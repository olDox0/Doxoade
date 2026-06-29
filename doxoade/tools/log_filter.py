# doxoade\tools\log_filter.py
# doxoade/tools/log_filter.py
"""
Suppress debug logging for user-facing commands (--help, --version, etc.)
Keeps logs only for actual operations.
"""
import sys
import logging
from typing import Callable, Optional


class CLILogFilter:
    """Filter that suppresses verbose logs for help/usage output."""
    
    # Commands that should suppress debug logs
    QUIET_COMMANDS = {
        '--help', '-h',
        '--version', '-v',
        '--refresh-help',
        '--guard',
    }
    
    @staticmethod
    def should_suppress_logs() -> bool:
        """Check if current invocation should suppress debug logs."""
        return any(cmd in sys.argv for cmd in CLILogFilter.QUIET_COMMANDS)
    
    @staticmethod
    def suppress_db_traces() -> None:
        """
        Suppress [DB-TRACE] logs from database modules.
        Call this early in cli() function.
        """
        import logging
        
        # Suppress specific loggers that produce [DB-TRACE] output
        loggers_to_suppress = [
            'doxoade.core_database',
            'doxoade.tools.db_utils',
            'doxoade.chronos',
            'doxoade.database',
            'doxoade.tools.command_metadata',
        ]
        
        # Only suppress if in quiet mode
        if CLILogFilter.should_suppress_logs():
            for logger_name in loggers_to_suppress:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.WARNING)
                # Optionally disable entirely
                logger.disabled = True


class DBTraceFilter(logging.Filter):
    """Logging filter to remove [DB-TRACE] messages."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter out DB-TRACE messages if in quiet mode.
        
        Args:
            record: Log record to filter
            
        Returns:
            False if message should be suppressed, True otherwise
        """
        if '[DB-TRACE]' in record.getMessage():
            return not CLILogFilter.should_suppress_logs()
        return True


def install_log_filter() -> None:
    """
    Install logging filter globally.
    Call once at module initialization.
    """
    # Get root logger
    root_logger = logging.getLogger()
    
    # Add filter
    db_filter = DBTraceFilter()
    root_logger.addFilter(db_filter)
    
    # Also suppress specific loggers in quiet mode
    if CLILogFilter.should_suppress_logs():
        CLILogFilter.suppress_db_traces()


# ============================================================================
# Integration with cli.py
# ============================================================================

"""
In cli.py @cli function, add at the START (before other code):

@click.group(cls=DoxoadeLazyGroup, invoke_without_command=True)
@click.option('--guard', is_flag=True, help='Verificação de integridade Aegis.')
@click.option('--refresh-help', is_flag=True, help='Força a atualização do cache de descrições.')
@click.pass_context
def cli(ctx, guard, refresh_help):
    \"\"\"olDox222 Advanced Development Environment (doxoade).\"\"\"
    
    # NEW: Suppress debug logs for help/version commands
    from doxoade.tools.log_filter import CLILogFilter
    CLILogFilter.suppress_db_traces()
    
    # ... rest of function ...
"""


# ============================================================================
# Alternative: Suppress at print source
# ============================================================================

"""
If the [DB-TRACE] output is coming from print() statements directly 
(not logging), you can wrap stdout:

class QuietWriter:
    def __init__(self, wrapped):
        self.wrapped = wrapped
    
    def write(self, s):
        # Suppress DB-TRACE lines
        if '[DB-TRACE]' not in s:
            self.wrapped.write(s)
    
    def flush(self):
        self.wrapped.flush()
    
    def __getattr__(self, name):
        return getattr(self.wrapped, name)

# In cli.py cli() function:
if CLILogFilter.should_suppress_logs():
    sys.stdout = QuietWriter(sys.stdout)
"""