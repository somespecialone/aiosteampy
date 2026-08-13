from aiosteampy.client.components.market.public import unwrap_data_envelope


class TestUnwrapDataEnvelope:
    def test_unwraps_enveloped_success_response(self):
        payload = {"success": True, "data": {"eCurrency": 1, "rgCompactBuyOrders": []}}

        assert unwrap_data_envelope({"data": payload}) is payload

    def test_unwraps_enveloped_error_response(self):
        payload = {"success": 15, "message": "Access Denied"}

        assert unwrap_data_envelope({"data": payload}) is payload

    def test_keeps_flat_response_unchanged(self):
        rj = {"success": 1, "data": {"eCurrency": 1, "rgCompactBuyOrders": []}}

        assert unwrap_data_envelope(rj) is rj

    def test_keeps_response_without_success_field_unchanged(self):
        rj = {"data": ["not", "a", "dict"]}

        assert unwrap_data_envelope(rj) is rj
