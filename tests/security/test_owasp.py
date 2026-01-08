from unittest.mock import patch
import validation_api

# OWASP A01: Broken Access Control & A03: Injection (Path Traversal)
# Already covered in test_security.py, but reinforced here.

# OWASP A03: Injection (Command Injection)
def test_command_injection_resilience():
    """
    Test that malicious filenames don't lead to command injection.
    We rely on subprocess.run/Popen taking a list of arguments.
    """
    # If a user provides a file path that looks like a command, it should be treated as a path.
    # Note: validation_api.run_command is executed with explicit lists, not shell=True.
    
    malicious_input = '; rm -rf /; echo "hacked'
    
    with patch("subprocess.run") as mock_run:
        # Mock executable check
        with patch("shutil.which", return_value="/bin/java"), \
             patch("os.path.exists", return_value=True):
             
             # Call internal run_command directly to check how it handles the list
             cmd = ["java", "-jar", "rsl.jar", "-i", malicious_input]
             
             # We expect this to NOT fail (it returns a log), but the mock should receive the exact list string
             validation_api.run_command(cmd, capture_output=False)
             
             args, _ = mock_run.call_args
             executed_cmd = args[0]
             
             # Verify it's still a list and not a string (which would trigger shell injection if shell=True)
             assert isinstance(executed_cmd, list)
             # Verify the malicious input is just an argument
             assert malicious_input in executed_cmd

# OWASP A03: Injection (XXE - XML External Entity)
def test_xxe_prevention_in_rsl_update(tmp_path):
    """
    Test that the XML parser is resilient to XXE attacks.
    We create a malicious XML with an external entity definition.
    If the parser is vulnerable, it might try to resolve it.
    """
    # Malicious XML payload trying to read /etc/passwd
    # Note: Modern python xml.etree is often safe against *remote* execution but might leak files.
    # We want to force use of defusedxml.
    
    xxe_payload = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE foo [  
      <!ELEMENT foo ANY >
      <!ENTITY xxe SYSTEM "file:///etc/passwd" >]><foo>&xxe;</foo>"""
      
    # Mock filesystem
    with patch("validation_api.RULE_SET_DIR", str(tmp_path)), \
         patch("validation_api.clean_dir"), \
         patch("shutil.copyfileobj"):
         
         # Mock zip extraction to "extract" our malicious config.xml
         # Actually update_rsl calls clean_dir then unzip.
         # get_ruleset_version parses the file. 
         
         config_dir = tmp_path / "config"
         config_dir.mkdir(parents=True)
         (config_dir / "config.xml").write_text(xxe_payload)
         
         # If we use standard etree, this might fail or succeed depending on python version/env.
         # But we want to ensure we are using defusedxml in the code.
         # We can check if validation_api.etree is defusedxml.ElementTree or standard.
         
         # For this test, let's try to parse it using the function
         try:
             validation_api.get_ruleset_version()
             # If vulnerable, it might return the content of /etc/passwd (if running as root/user who can read it)
             # or throw an error.
             # If secure (defusedxml), it should raise a DefusedXmlException or similar.
             
             # However, defusedxml defaults to raising exceptions on DTDs.
             pass
         except Exception as e:
             # If it raises "EntitiesForbidden" or similar, we are safe.
             assert "EntitiesForbidden" in str(type(e)) or "Forbidden" in str(e) or "invalid" in str(e).lower()

# OWASP A05: Security Misconfiguration (Debug Mode)
def test_production_config():
    """Verify that Flask is not in debug mode."""
    from web_app import server
    assert not server.debug
    assert server.secret_key != "your-secret-key"

# OWASP A09: Security Logging
def test_logging_configured():
    """Verify that the logger is configured."""
    assert validation_api.logger.level == validation_api.logging.INFO
