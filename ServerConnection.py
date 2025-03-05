
from sshtunnel import SSHTunnelForwarder  # type: ignore
import requests
import paramiko


JUMP_HOST = "login-stud.informatik.uni-bonn.de"
JUMP_USER = "shawkiy1"

TARGET_HOST = "auerkamp.cs.uni-bonn.de"
TARGET_USER = "shawki"

LOCAL_PORT = 7000

RUNNING_PORT = 5000


class ServerConnection:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ServerConnection, cls).__new__(cls)
        return cls._instance

    def __init__(        
        self,
        jump_host=JUMP_HOST,
        jump_user=JUMP_USER,
        target_host=TARGET_HOST,
        target_user=TARGET_USER,
        local_port=LOCAL_PORT,
    ):
        """
        Initializes the connection utility with the given parameters.

        Parameters:
        jump_host (str): The hostname of the jump server.
        jump_user (str): The username for the jump server.
        target_host (str): The hostname of the target server.
        target_user (str): The username for the target server.
        local_port (int): The local port to use for the connection.

        Note:
        This initializer ensures that it is only called once by checking the 'initialized' attribute.
        """
        if not hasattr(self, "initialized"):  # Ensure __init__ is only called once
            self.jump_host = jump_host
            self.jump_user = jump_user
            self.target_host = target_host
            self.target_user = target_user
            self.local_port = local_port
            self.tunnel = None
            self.target_client = None
            self.initialized = True

    def open_connection(self) -> bool:
        """
        Establishes an SSH tunnel to a target host through a jump host and opens an SSH connection to the target host.

        Returns:
            bool: True if the connection is successfully established, False otherwise.

        Raises:
            Exception: If there is an error during the connection process, it will be caught and printed.
        """
        try:
            self.tunnel = SSHTunnelForwarder(
                (self.jump_host, 22),
                ssh_username=self.jump_user,
                remote_bind_address=(
                    self.target_host,
                    22,
                ),
                local_bind_address=("127.0.0.1", self.local_port),
            )
            self.tunnel.start()

            self.target_client = paramiko.SSHClient()
            self.target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.target_client.connect(
                "127.0.0.1", port=self.local_port, username=self.target_user
            )
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def close_connection(self):
        """
        Closes the connection to the target client and stops the tunnel if they exist.

        This method checks if the `target_client` and `tunnel` attributes are set. 
        If `target_client` is set, it closes the connection to the target client. 
        If `tunnel` is set, it stops the tunnel. 
        Finally, it prints a message indicating that the connection has been closed.
        """
        if self.target_client:
            self.target_client.close()
        if self.tunnel:
            self.tunnel.stop()
        print("Connection closed.")

    def send_api_post(self, endpoint, data={}, timeout=5):
        """
        Sends a POST request to the specified API endpoint.

        Args:
            endpoint (str): The API endpoint to send the request to.
            data (dict, optional): The JSON data to include in the POST request. Defaults to an empty dictionary.
            timeout (int, optional): The timeout for the request in seconds. Defaults to 5.

        Returns:
            response (requests.Response or None): The response object from the POST request, or None if an error occurred.

        Raises:
            Exception: If an error occurs during the request, it is raised after being printed.
        """
        api_url = rf"http://127.0.0.1:{RUNNING_PORT}/{endpoint}"

        try:
            response = requests.post(api_url, json=data, timeout=timeout)
        except Exception as e:
            response = None
            print(f"Error: {e}")
            raise e

        return response

    def send_api_get(self, endpoint, data={},timeout=5):
        """
        Sends a GET request to the specified API endpoint.

        Args:
            endpoint (str): The API endpoint to send the GET request to.
            timeout (int, optional): The timeout for the GET request in seconds. Defaults to 5.

        Returns:
            response (requests.Response or None): The response object from the GET request, or None if an exception occurred.

        Raises:
            Exception: If an error occurs during the GET request.
        """
        api_url = rf"http://127.0.0.1:{RUNNING_PORT}/{endpoint}"

        try:
            response = requests.get(api_url, json=data ,timeout=timeout)
        except Exception as e:
            response = None
            print(f"Error: {e}")
            raise e

        return response


    def get_functions(self):

        response = self.send_api_get("functions", timeout=5)
        response.raise_for_status()

        return_value = response.json()["available"]

        return return_value

    def cube_number(self, number):

        response = self.send_api_post(
            "cube",
            {"number": number},timeout=10,
        )
        response.raise_for_status()

        return response.json()["cubed"]
    

    def get_image(self, batch_number, img_number):
        response = self.send_api_get("get-image",
                                     {"batch_number": batch_number, "img_number": img_number},
                                     timeout=10,)
        response.raise_for_status()

        return response.json()["image"]
    

    def get_dataframe(self):
        response = self.send_api_get("get-dataframe", timeout=10)
        response.raise_for_status()

        return response.json()["dataframe"]





if __name__ == "__main__":
    conn = ServerConnection()
    conn.open_connection()
    
    print(f"{conn.get_functions() = }")
    print(f"{conn.cube_number(3) = }")
    print(f"{conn.cube_number(10) = }")
    
    conn.close_connection()
    
    