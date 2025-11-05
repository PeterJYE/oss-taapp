import httpx
import pytest


@pytest.mark.unit
def test_client_headers_cookies_and_context_manager():
    pytest.importorskip("generated_client.mail_client_service_client.client")

    from generated_client.mail_client_service_client.client import Client

    c = Client(base_url="http://example.com")

    hc = c.get_httpx_client()
    assert isinstance(hc, httpx.Client)

    c2 = c.with_headers({"X-Test": "1"})
    assert hc.headers.get("X-Test") == "1"
    assert c2 is not None

    c.with_cookies({"session": "abc"})
    assert hc.cookies.get("session") == "abc"

    c.with_timeout(httpx.Timeout(5.0))
    assert isinstance(hc.timeout, httpx.Timeout)

    custom = httpx.Client(base_url="http://example.com")
    c5 = c.set_httpx_client(custom)
    assert c5.get_httpx_client() is custom

    with Client(base_url="http://example.com") as ctx:
        assert isinstance(ctx.get_httpx_client(), httpx.Client)


@pytest.mark.unit
def test_authenticated_client_sets_auth_header():
    pytest.importorskip("generated_client.mail_client_service_client.client")

    from generated_client.mail_client_service_client.client import AuthenticatedClient

    ac = AuthenticatedClient(base_url="http://example.com", token="secrettoken")
    hc = ac.get_httpx_client()
    assert hc.headers.get(ac.auth_header_name) is not None
    assert "secrettoken" in hc.headers.get(ac.auth_header_name)

    custom = httpx.Client(base_url="http://example.com")
    ac2 = ac.set_httpx_client(custom)
    assert ac2.get_httpx_client() is custom

    ac3 = ac.with_headers({"X-Foo": "bar"})
    assert isinstance(ac3, AuthenticatedClient)
