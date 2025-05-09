class Version:
  def version(self):
    return "1.0.0"
  
  def git_revision(self):
    import os
    import subprocess
    from pathlib import Path
    
    # Get the directory one level higher than version.py
    project_dir = Path(__file__).resolve().parent.parent
    git_dir = project_dir / ".git"
    
    if not git_dir.exists():
      return None
    
    try:
      # Get the current git commit hash
      commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], 
        cwd=project_dir
      ).decode('utf-8').strip()
      
      # Check if there are uncommitted changes
      status_output = subprocess.check_output(
        ["git", "status", "--porcelain"], 
        cwd=project_dir
      ).decode('utf-8').strip()
      
      if status_output:
        commit_hash += "*"
        
      return commit_hash
    except subprocess.CalledProcessError:
      return None
  
  def hash(self):
    return { "version": self.version(), "git": self.git_revision() }
  
  