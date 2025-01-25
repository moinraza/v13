import json
from app.quotexapi.ws.channels.base import Base
from app.quotexapi.expiration import get_expiration_time_quotex


class Buy(Base):
    """Class for Quotex buy websocket channel."""

    name = "buy"

    def __call__(self, price, asset, direction, duration, request_id):
        account_type = self.api.account_type
        option_type = 100
        if "_otc" not in asset:
            option_type = 1
            duration = get_expiration_time_quotex(
                int(self.api.timesync.server_timestamp),
                duration
            )

        payload = {
            "asset": asset,
            "amount": price,
            "time": duration,
            "action": direction,
            "isDemo": account_type,
            "tournamentId": 0,
            "requestId": request_id,
            "optionType": option_type
        }

        data = f'42["orders/open",{json.dumps(payload)}]'
        self.send_websocket_request(data)
