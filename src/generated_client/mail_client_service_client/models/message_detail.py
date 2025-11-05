from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="MessageDetail")


@_attrs_define
class MessageDetail:
    """Complete message details.

    Attributes:
        id (str):
        from_ (str):
        to (str):
        date (str):
        subject (str):
        body (str):
    """

    id: str
    from_: str
    to: str
    date: str
    subject: str
    body: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        from_ = self.from_

        to = self.to

        date = self.date

        subject = self.subject

        body = self.body

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "from_": from_,
                "to": to,
                "date": date,
                "subject": subject,
                "body": body,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        from_ = d.pop("from_")

        to = d.pop("to")

        date = d.pop("date")

        subject = d.pop("subject")

        body = d.pop("body")

        message_detail = cls(
            id=id,
            from_=from_,
            to=to,
            date=date,
            subject=subject,
            body=body,
        )

        message_detail.additional_properties = d
        return message_detail

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
