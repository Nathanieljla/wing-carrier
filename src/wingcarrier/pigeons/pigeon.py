import sys
import os
import importlib
import subprocess

import __main__

class Pigeon(object):
    def __init__(self, *args, **kwargs):
        pass
    
    
    @staticmethod
    def decode(output):
        try:
            return output.decode('utf-8')
        except UnicodeDecodeError:
            return output.decode('latin-1')
        
        
        
    @staticmethod
    def encode(output):
        try:
            return output.encode('utf-8')
        except UnicodeEncodeError:
            return output.encode('latin-1')        
        
    
    
    @classmethod
    def get_temp_filename(cls):
        """the name of the temporary file wing will use in write_temp_file()
        
        Sub-classes can override this is they want a unique name for their
        Pigeon.
        """
        return('wing_output_text.txt')
    
    

    @classmethod
    def get_temp_filepath(cls):
        """Returns the full path of the temp file on the local system."""
        return os.path.join(os.environ['TMP'], cls.get_temp_filename())



    @classmethod
    def write_temp_file(cls, txt):
        """writes the input text to the get_temp_filepath()"""
    
        # Save the text to a temp file. If we're dealing with mel, make sure it
        # ends with a semicolon, or Maya could become angered!
        #txt = get_wing_text()
        temp_path = cls.get_temp_filepath()
        f = open(temp_path, "wb")
    
        print('writing temp file:{}'.format(temp_path))
        f.write(Pigeon.encode(txt))
    
        f.close()

        temp_path = temp_path.replace("\\", "/")
        return temp_path
    
    

    @staticmethod
    def read_file(file_path):
        """Executes the python code stored in the file path.
        
        Args:
            file_path (string) : The absolute file path of the py file to read
        
        """
        
        print("WING: executing code from file {}\n".format(file_path))
        if os.access(file_path, os.F_OK):
            # execute the file contents in Maya:
            with open(file_path, "rb") as f:
                data = f.read()
                data = Pigeon.decode(data)
                exec(data, __main__.__dict__, __main__.__dict__) 

        else:
            print("No Wing-generated temp file exists: " + file_path)
            
            
            
    @classmethod
    def post_module_import(cls, module):
        """called if a Pigeon.import_module() is successful.
        
        The default behavior is to call the run() on the module if one
        exists. Override this method in a sub-class if you have custom logic
        for how you want what happens after a module has been
        imported/reloaded.
        
        Args:
            module : The module that was imported/reloaded from import_module()
        """
        if hasattr(module, 'run'):
            module.run()
            
            

    @classmethod
    def import_module(cls, module_name, file_path):
        """Attempts to import/reload the input module name and execute any run()
        
        If importing/reloading fails, then the file path is read (if
        defined). If sub-classes don't want to call run() they should
        override post_module_import().
        
        Args:
            module_name (string) : The name of the module relative to any
            package namespace.
            file_path (string) : The absolute file path to the py file.
        """
        
        print('\n')
        imported = module_name in sys.modules
        if imported:
            print('reloading module:{0}'.format(module_name))
            importlib.reload(sys.modules[module_name])
        else:
            try:
                print('Attempting module import of:{0}'.format(module_name))
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                if file_path:
                    cls.read_file(file_path)


        if module_name in sys.modules:
            cls.post_module_import(sys.modules[module_name])
    
    

    def can_dispatch(self):
        """Check if conditions are right to send code to application
        
        can_dispatch() is used to determine what dispatcher wing will use
        with when there's no active dispatcher found.
        """
        raise NotImplementedError
    
    
    def owns_process(self, process):
        """Returns true if the process is the pigeon's target application
        
        This is used when an external application is connects to wing. When True
        is returned the Dispatcher becomes the active dispatcher to send commands
        to.
        
        Args:
            process (psutils.Process) : The node to remove the data from.  
        """
        raise NotImplementedError
    

    def send(self, highlighted_text, module_path, file_path, doc_type):
        """The main entry point for sending content from wing to an external app
        
        sub-classes should override this with application specfic logic for how
        the data is sent to an external application.        
        """
        raise NotImplementedError
    
    
    def send_python_command(self, command_string):
        """Send a custom python command to the target application
        
        Returns:
            bool : True if the command was successfully sent.        
        """
        raise NotImplementedError
    
    
    @staticmethod
    def get_exe_path_from_pid(pid):
        """
        Retrieves the executable path of a process given its PID using subprocess.
    
        Args:
            pid: The process ID (integer).
    
        Returns:
            The executable path (string) if found, otherwise None.
        """
        try:
            command = f'wmic process where processid={pid} get executablepath /value'
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            output_lines = result.stdout.strip().split('\n')
            
            for line in output_lines:
                if 'ExecutablePath=' in line:
                    exe_path = line.split('=')[1].strip()
                    return exe_path
        except subprocess.CalledProcessError:
            return None
        except FileNotFoundError:
            return None
        return None
    
    @staticmethod
    def process_id(process_name):
        """Returns the process ID of the running cascadeur.exe or None"""
        
        import subprocess
        call = 'TASKLIST', '/FI', 'imagename eq %s' % process_name
        # use buildin check_output right away
        output = Pigeon.decode(subprocess.check_output(call))
    
        # check in last line for process name
        last_line = output.split('\r\n')
        if len(last_line) < 3:
            return None
        
        #first result is 3 because the headers
        #or in case more than one, you can use the last one using [-2] index
        data = " ".join(last_line[3].split()).split()  
    
        #return a list with the name and pid 
        return data[1]     


