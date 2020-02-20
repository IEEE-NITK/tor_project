from typing import List
from connection.node import Node
from connection.skt import Skt
from crypto.core_crypto import CoreCryptoDH
from cell.cell_processing import Builder, Parser, Processor
from cell.serializers import Serialize, Deserialize


class Circuit:
	"""
	The class representing the Circuit object for the Onion Proxy.
	"""

	@staticmethod
	def get_rand_circ_id(current_circ_id: int) -> int:
		"""
		Returns a circId for the circuit. To prevent circId collisions, it increments the previous circId.
		:return: circId --> integer
		"""
		circ_id = current_circ_id + 1
		return circ_id

	def __init__(self, node_container: List[Node], skt: Skt, circ_id: int):
		"""
		Constructor
		:param circ_id: The circuit Id for the given circuit
		:param node_container: The list of Node objects including the Client itself
		:param skt: The Client's socket object. We will use this to connect to the nodes in the container
		"""
		self.circ_id = circ_id
		self.node_container = node_container
		self.skt = skt
		self.session_key01 = None
		self.session_key02 = None
		self.session_key03 = None

	def open_connection(self, hop_i: int) -> int:
		"""

		:param hop_i: The index of the node in the node container that the client wants to connect to
		:return: Returns a status code. 0 --> Success and -1 means error
		"""
		err_code = self.skt.client_connect(self.node_container[hop_i].host, self.node_container[hop_i].port)
		if err_code == 0:
			return 0
		else:
			return -1

	def create_circuit_hop1(self) -> int:
		"""
		The function to setup circuit with the first hop in the circuit. Creates the CREATE/CREATE2 cell and sends it
		down the socket. It assumes that the open_connection was called on the first node and the socket is connected
		to the first node
		:return: Returns a status code. 0 --> Success DH Handshake and -1 --> Means error in processing the cell or the DH Handshake.
		On error it closes the socket to node 1
		"""
		# First create a CREATE2 Cell.
		x, x_bytes, gx, gx_bytes = CoreCryptoDH.generate_dh_priv_key()
		create_cell = Builder.build_create_cell('TAP', x_bytes, gx_bytes, self.circ_id, self.node_container[1].onion_key_pub)

		# Sending a JSON String down the socket
		self.skt.client_send_data(Serialize.obj_to_json(create_cell).encode('utf-8'))

		# Get the created cell in response and convert it to python Cell Object
		recv_data = self.skt.client_recv_data().decode('utf-8')
		dict_cell = Deserialize.json_to_dict(recv_data)
		created_cell = Parser.parse_created_cell(dict_cell)

		self.session_key01 = Processor.process_created_cell(created_cell, self.circ_id, x_bytes)
		if self.session_key01 is None:
			self.skt.close()
			return -1

		return 0

	def create_circuit_hop2(self) -> int:
		"""
		The function to setup circuit with the second hop in the circuit. Creates the EXTEND/EXTEND2 cell and sends it
		down the socket. It assumes that the open_connection was called on the first node and the socket is connected
		to the first node, and that to the second node
		:return: Returns a status code. 0 --> Success DH Handshake and -1 --> Means error in processing the cell or the DH Handshake.
		On error it closes the socket to node 2.
		"""
		# First create a EXTEND2 Cell.
		x, x_bytes, gx, gx_bytes = CoreCryptoDH.generate_dh_priv_key()

		# For hop2 we get its IP:port for LSPEC ==> Link specifier
		hop2_ip = str(self.node_container[2].host)
		hop2_port = str(self.node_container[2].port)
		extend_cell = Builder.build_extend_cell('TAP', x_bytes, gx_bytes, self.circ_id, self.node_container[2].onion_key_pub, hop2_ip+':'+hop2_port)

		print(Serialize.obj_to_json(extend_cell))

		# Sending a JSON String down the socket
		self.skt.client_send_data(Serialize.obj_to_json(extend_cell).encode('utf-8'))

		# Get the extended cell in response and convert it to python Cell Object
		recv_data = self.skt.client_recv_data().decode('utf-8')
		dict_cell = Deserialize.json_to_dict(recv_data)
		extended_cell = Parser.parse_extended_cell(dict_cell)

		self.session_key02 = Processor.process_extended_cell(extended_cell, self.circ_id, x_bytes)
		if self.session_key02 is None:
			self.skt.close()
			return -1

		return 0
