import argparse
import asyncio
import logging
from typing import Dict, Optional
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived
from aioquic.tls import SessionTicket

logger = logging.getLogger("server")

class DosServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.migration_count = 0

    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, StreamDataReceived):
            self.migration_count += 1
            if self.migration_count % 1000 == 0:
                logger.info(f"Received {self.migration_count} migrations")

class SessionTicketStore:
    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}
    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket
    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)

async def main(host, port, configuration, session_ticket_store):
    logger.info(f"Starting QUIC server on {host}:{port}")
    await serve(
        host, port,
        configuration=configuration,
        create_protocol=DosServerProtocol,
        session_ticket_fetcher=session_ticket_store.pop,
        session_ticket_handler=session_ticket_store.add,
    )
    await asyncio.Future()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="::")
    parser.add_argument("--port", type=int, default=4444)
    parser.add_argument("-k", "--private-key", type=str)
    parser.add_argument("-c", "--certificate", type=str, required=True)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    configuration = QuicConfiguration(alpn_protocols=["dos-demo"], is_client=False)
    configuration.load_cert_chain(args.certificate, args.private_key)

    try:
        asyncio.run(main(
            host=args.host,
            port=args.port,
            configuration=configuration,
            session_ticket_store=SessionTicketStore(),
        ))
    except KeyboardInterrupt:
        logger.info("Server stopped")
