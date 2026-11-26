import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.catalogue import ProductDocument, ProductPage


class CategoryWrite(BaseModel):
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=3000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    image_url: HttpUrl | None = None
    catalog_pdf_url: str | None = Field(default=None, min_length=8, max_length=1000, pattern=r"^https://")
    catalog_pdf_title: str | None = Field(default=None, max_length=180)

    @field_validator("catalog_pdf_url", "catalog_pdf_title", mode="before")
    @classmethod
    def blank_pdf_fields_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class CategoryPatch(BaseModel):
    slug: str | None = Field(default=None, min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=3000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    image_url: HttpUrl | None = None
    catalog_pdf_url: str | None = Field(default=None, min_length=8, max_length=1000, pattern=r"^https://")
    catalog_pdf_title: str | None = Field(default=None, max_length=180)

    @field_validator("catalog_pdf_url", "catalog_pdf_title", mode="before")
    @classmethod
    def blank_pdf_fields_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class CategoryAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    description: str | None
    sort_order: int
    image_url: str | None
    wordpress_source_id: str | None
    is_app_collection: bool = True
    cms_locked: bool = False
    product_count: int = 0
    is_published: bool
    has_draft: bool
    catalog_pdf_url: str | None = None
    catalog_pdf_title: str | None = None
    published_payload: dict[str, object] | None = None


class CollectionProductsWrite(BaseModel):
    product_ids: list[UUID]
    previous_product_ids: list[UUID] | None = None

    @field_validator("product_ids")
    @classmethod
    def dedupe_product_ids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))


class CategoryBulkVisibilityWrite(BaseModel):
    category_ids: list[UUID] = Field(min_length=1, max_length=200)
    is_published: bool


class ProductCategoryOverrideWrite(BaseModel):
    category_id: UUID
    category_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def include_primary_category(self) -> "ProductCategoryOverrideWrite":
        self.category_ids = list(dict.fromkeys([self.category_id, *self.category_ids]))
        return self


class ProductBulkCategoryWrite(BaseModel):
    product_ids: list[UUID] = Field(min_length=1, max_length=200)
    category_id: UUID
    keep_secondary_categories: bool = True


class ProductPdfOverrideWrite(BaseModel):
    title: str = Field(default="Product catalogue PDF", min_length=1, max_length=180)
    url: str = Field(min_length=8, max_length=1000, pattern=r"^https://")


class CatalogueSummaryAdmin(BaseModel):
    products_total: int
    products_published: int
    products_missing_pdf: int
    products_category_overridden: int
    products_pdf_overridden: int
    products_unassigned: int = 0
    categories_total: int
    categories_published: int
    categories_hidden: int
    categories_empty: int
    categories_missing_pdf: int
    wordpress_tags_total: int = 0
    open_service_requests: int
    open_quote_requests: int
    open_contact_inquiries: int
    customers_total: int


class CategoryCatalogueWrite(BaseModel):
    category_key: str = Field(min_length=1, max_length=180)
    category_id: UUID | None = None
    wordpress_category_id: str | None = Field(default=None, max_length=160)
    title: str = Field(default="Category catalogue PDF", min_length=1, max_length=180)
    catalog_pdf_url: str = Field(min_length=8, max_length=1000, pattern=r"^https://")


class CategoryCatalogueAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_key: str
    category_id: UUID | None
    wordpress_category_id: str | None
    title: str
    catalog_pdf_url: str
    source: str
    updated_at: str


class ProductWrite(BaseModel):
    category_id: UUID
    category_ids: list[UUID] = Field(default_factory=list, max_length=50)
    slug: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=2, max_length=220)
    model_code: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=12000)
    applications: list[str] = Field(default_factory=list, max_length=24)
    features: list[str] = Field(default_factory=list, max_length=32)
    specifications: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)
    image_url: HttpUrl | None = None
    gallery_images: list[HttpUrl] = Field(default_factory=list, max_length=16)
    price_minor: int | None = Field(default=None, ge=0, le=999_999_999_999)
    currency_code: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    currency_minor_unit: int = Field(default=2, ge=0, le=4)
    stock_status: Literal["instock", "outofstock", "onbackorder", "unknown"] = "unknown"
    stock_quantity: int | None = Field(default=None, ge=0, le=10_000_000)
    documents: list[ProductDocument] = Field(default_factory=list, max_length=24)
    source_reference: str | None = Field(default=None, max_length=500)
    wordpress_source_id: str | None = Field(default=None, max_length=160)
    wordpress_source_url: HttpUrl | None = None

    @model_validator(mode="after")
    def include_primary_category(self) -> "ProductWrite":
        self.category_ids = list(dict.fromkeys([self.category_id, *self.category_ids]))
        return self

    @field_validator("applications", "features")
    @classmethod
    def normalize_bounded_text(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 180 for value in cleaned):
            raise ValueError("Each entry must be 180 characters or fewer")
        return cleaned

    @field_validator("specifications")
    @classmethod
    def validate_specification_fields(cls, values: dict[str, object]) -> dict[str, object]:
        if len(values) > 60:
            raise ValueError("A product can contain at most 60 specification fields")
        if any(not key.strip() or len(key) > 80 for key in values):
            raise ValueError("Specification field names must be between 1 and 80 characters")
        return values


class ProductPatch(BaseModel):
    category_id: UUID | None = None
    category_ids: list[UUID] | None = Field(default=None, max_length=50)
    slug: str | None = Field(default=None, min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str | None = Field(default=None, min_length=2, max_length=220)
    model_code: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=12000)
    applications: list[str] | None = Field(default=None, max_length=24)
    features: list[str] | None = Field(default=None, max_length=32)
    specifications: dict[str, str | int | float | bool | list[str]] | None = None
    image_url: HttpUrl | None = None
    gallery_images: list[HttpUrl] | None = Field(default=None, max_length=16)
    price_minor: int | None = Field(default=None, ge=0, le=999_999_999_999)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    currency_minor_unit: int | None = Field(default=None, ge=0, le=4)
    stock_status: Literal["instock", "outofstock", "onbackorder", "unknown"] | None = None
    stock_quantity: int | None = Field(default=None, ge=0, le=10_000_000)
    documents: list[ProductDocument] | None = Field(default=None, max_length=24)
    source_reference: str | None = Field(default=None, max_length=500)
    wordpress_source_id: str | None = Field(default=None, max_length=160)
    wordpress_source_url: HttpUrl | None = None


class ProductAdmin(BaseModel):
    id: UUID
    category_id: UUID
    category_ids: list[UUID]
    slug: str
    name: str
    model_code: str | None
    summary: str | None
    description: str | None
    applications: list[str]
    features: list[str]
    specifications: dict[str, object]
    image_url: str | None
    gallery_images: list[str]
    price_minor: int | None
    currency_code: str
    currency_minor_unit: int
    stock_status: str
    stock_quantity: int | None
    documents: list[ProductDocument]
    catalog_pdf_url: str | None = None
    catalog_pdf_source: Literal["product", "category", "none"] = "none"
    source_reference: str | None
    wordpress_source_id: str | None
    wordpress_source_url: str | None
    category_override: bool = False
    documents_override: bool = False
    own_documents: list[ProductDocument] = Field(default_factory=list)
    app_collection_ids: list[UUID] = Field(default_factory=list)
    wordpress_tag_ids: list[UUID] = Field(default_factory=list)
    is_published: bool
    has_draft: bool
    updated_at: str
    published_payload: dict[str, object] | None = None


class ProductAdminPage(ProductPage):
    # Admin list endpoints build ProductAdmin objects directly. Keep the page
    # item type identical so Pydantic does not reject the base model instances.
    items: list[ProductAdmin]


class HomeContent(BaseModel):
    search_hint: str = Field(default="Search products, models, applications…", max_length=120)
    hero_title: str = Field(default="", max_length=120)
    hero_description: str = Field(default="", max_length=500)
    hero_cta_label: str = Field(default="", max_length=60)
    hero_cta_target: Literal["products", "solution_finder", "quote", "support"] = "solution_finder"
    intent_section_title: str = Field(default="What are you looking for?", max_length=100)
    products_card_title: str = Field(default="Explore products", max_length=80)
    products_card_subtitle: str = Field(default="Browse the catalogue", max_length=120)
    solution_card_title: str = Field(default="Find a solution", max_length=80)
    solution_card_subtitle: str = Field(default="Guided requirement", max_length=120)
    quote_card_title: str = Field(default="Request a quote", max_length=80)
    quote_card_subtitle: str = Field(default="Tell us what you need", max_length=120)
    support_card_title: str = Field(default="Service & support", max_length=80)
    support_card_subtitle: str = Field(default="Get help with equipment", max_length=120)
    announcement_title: str = Field(default="", max_length=120)
    announcement_body: str = Field(default="", max_length=500)
    announcement_visible: bool = False
    featured_category_ids: list[UUID] = Field(default_factory=list, max_length=12)
    featured_product_category_ids: list[UUID] = Field(default_factory=list, max_length=12)
    featured_products_title: str = Field(default="Featured products", max_length=80)
    featured_product_ids: list[UUID] = Field(default_factory=list, max_length=12)
    section_order: list[Literal["categories", "featured_products", "requests", "announcements"]] = Field(default_factory=lambda: ["categories", "featured_products", "requests", "announcements"], max_length=4)
    visible_sections: list[Literal["categories", "featured_products", "requests", "announcements"]] = Field(default_factory=lambda: ["categories", "featured_products", "requests", "announcements"], max_length=4)


class ContactContent(BaseModel):
    sales_phone: str = Field(default="", max_length=40)
    support_phone: str = Field(default="", max_length=40)
    whatsapp_number: str = Field(default="", max_length=40)
    sales_email: str = Field(default="", max_length=254)
    support_email: str = Field(default="", max_length=254)
    office_address: str = Field(default="", max_length=1200)
    support_hours: str = Field(default="", max_length=500)
    availability_message: str = Field(default="", max_length=500)


class SolutionFinderContent(BaseModel):
    application_options: list[str] = Field(
        default_factory=lambda: [
            "Factory / Industrial machinery",
            "Office / Commercial",
            "Hospital / Medical equipment",
            "Server room / Data centre",
            "Home / Residential",
            "Solar / Battery storage",
            "Other",
        ],
        min_length=1,
        max_length=20,
    )
    step_titles: list[str] = Field(
        default_factory=lambda: [
            "Where do you need power protection?",
            "What needs power?",
            "Do you know the capacity?",
            "Where is the project?",
            "When do you need it?",
        ],
        min_length=5,
        max_length=5,
    )
    application_prompt: str = Field(default="Choose the application that best describes your requirement.", max_length=500)
    general_prompt: str = Field(default="Share what you know. You can skip technical details you are unsure about.", max_length=500)

    @field_validator("application_options", "step_titles")
    @classmethod
    def validate_nonempty_options(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 180 for value in cleaned):
            raise ValueError("Options must be non-empty and no longer than 180 characters")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("Options must be unique")
        return cleaned


class ChatContent(BaseModel):
    model_config = ConfigDict(validate_default=True)

    enabled: bool = False
    integration: Literal["iframe", "hosted_widget"] = "hosted_widget"
    embed_url: HttpUrl | None = "https://enertechups.cloud"
    widget_script_url: HttpUrl | None = "https://enertechups.cloud/widget.js"
    welcome_message: str = Field(default="", max_length=500)
    fallback_message: str = Field(default="", max_length=500)
    human_handoff_url: HttpUrl | None = None
    human_handoff_enabled: bool = False


class BrandContent(BaseModel):
    display_name: str = Field(default="EnerTech", min_length=1, max_length=80)
    logo_url: HttpUrl | None = None
    support_icon_url: HttpUrl | None = None


class ContentEnvelope(BaseModel):
    key: str
    draft_payload: dict[str, object]
    published_payload: dict[str, object] | None
    draft_revision: int
    published_revision: int | None
    updated_at: str | None


class ServiceRequestWrite(BaseModel):
    product_model: str = Field(min_length=1, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    problem_category: Literal["alarm", "battery", "performance", "installation", "other"]
    description: str = Field(min_length=10, max_length=4000)
    service_location: str = Field(min_length=2, max_length=500)
    attachments: list[HttpUrl] = Field(default_factory=list, max_length=5)


class QuoteRequestWrite(BaseModel):
    application: str = Field(min_length=2, max_length=180)
    equipment_or_load: str = Field(min_length=2, max_length=1000)
    capacity_known: bool = False
    capacity: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=1, le=100000)
    project_location: str = Field(default="", max_length=500)
    expected_timeline: str = Field(default="", max_length=300)


class CustomerRequestPublic(BaseModel):
    id: UUID
    kind: Literal["service", "quote"]
    status: str
    payload: dict[str, object]
    resolution_note: str | None
    created_at: str
    updated_at: str


class CustomerRequestAdmin(CustomerRequestPublic):
    customer_uid: str
    customer_email: str
    assigned_to: str | None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_company: str | None = None
    customer_location: str | None = None


class CustomerRequestUpdate(BaseModel):
    status: Literal["submitted", "in_review", "assigned", "waiting_for_customer", "resolved", "quote_preparing", "quote_sent", "closed"]
    assigned_to: str | None = Field(default=None, max_length=128)
    resolution_note: str | None = Field(default=None, max_length=2000)


class KnowledgeWrite(BaseModel):
    slug: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=3, max_length=220)
    category: str = Field(default="General", min_length=2, max_length=100)
    answer: str = Field(min_length=10, max_length=12000)
    source_reference: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=10000)


class KnowledgePatch(BaseModel):
    slug: str | None = Field(default=None, min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str | None = Field(default=None, min_length=3, max_length=220)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    answer: str | None = Field(default=None, min_length=10, max_length=12000)
    source_reference: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class KnowledgeAdmin(BaseModel):
    id: UUID
    slug: str
    title: str
    category: str
    answer: str
    source_reference: str | None
    sort_order: int
    is_published: bool
    has_draft: bool


class KnowledgePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    category: str
    answer: str


class CustomerProfileWrite(BaseModel):
    customer_type: Literal["end_user", "reseller", "epc", "distributor"]
    name: str = Field(min_length=2, max_length=180)
    mobile_number: str = Field(min_length=7, max_length=24, pattern=r"^[+0-9()\-\s]+$")
    email: str = Field(min_length=5, max_length=254)
    location: str = Field(min_length=2, max_length=500)
    company_name: str | None = Field(default=None, max_length=220)
    gst_number: str | None = Field(default=None, max_length=32)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("name", "location")
    @classmethod
    def normalize_required_profile_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Enter at least 2 characters")
        return normalized

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile_number(cls, value: str) -> str:
        normalized = value.strip()
        digits = "".join(character for character in normalized if character.isdigit())
        if not re.fullmatch(r"\+?[0-9()\-\s]+", normalized) or not 10 <= len(digits) <= 15:
            raise ValueError("Enter a phone number with 10 to 15 digits")
        return normalized

    @field_validator("company_name", "gst_number")
    @classmethod
    def normalize_optional_business_fields(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("gst_number")
    @classmethod
    def normalize_gst_number(cls, value: str | None) -> str | None:
        normalized = value.strip().upper() if value and value.strip() else None
        if normalized and not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", normalized):
            raise ValueError("Enter a valid 15-character GSTIN")
        return normalized

    @field_validator("company_name")
    @classmethod
    def require_company_name_for_business(cls, value: str | None, info) -> str | None:
        if info.data.get("customer_type") != "end_user" and (value is None or len(value) < 2):
            raise ValueError("Company name is required for reseller, EPC, and distributor accounts")
        return value

    @field_validator("gst_number")
    @classmethod
    def require_gst_for_business(cls, value: str | None, info) -> str | None:
        if info.data.get("customer_type") != "end_user" and not value:
            raise ValueError("GST number is required for reseller, EPC, and distributor accounts")
        return value


class CustomerProfilePublic(BaseModel):
    id: UUID
    customer_type: Literal["end_user", "reseller", "epc", "distributor"]
    name: str
    mobile_number: str
    email: str
    location: str
    company_name: str | None
    gst_number: str | None
    created_at: str
    updated_at: str


class AdminAccountWrite(BaseModel):
    firebase_uid: str = Field(min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=254)
    display_name: str | None = Field(default=None, max_length=180)
    role: Literal["content_editor", "admin", "super_admin"] = "content_editor"
    is_active: bool = True


class AdminAccountPublic(BaseModel):
    id: UUID
    firebase_uid: str
    email: str | None
    display_name: str | None
    role: Literal["content_editor", "admin", "super_admin"]
    is_active: bool
    created_at: str
    updated_at: str


class AuditEventPublic(BaseModel):
    id: UUID
    actor_uid: str
    action: str
    entity_type: str
    entity_id: str
    change_summary: dict[str, object]
    created_at: str


class ContactInquiryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    phone: str = Field(min_length=7, max_length=24)
    company_name: str | None = Field(default=None, max_length=220)
    subject: str | None = Field(default=None, max_length=220)
    message: str = Field(min_length=5, max_length=10000)
    inquiry_type: Literal["general", "sales", "product", "service"] = "general"

    @field_validator("name", "phone", "message", mode="before")
    @classmethod
    def strip_contact_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("company_name", "subject", mode="before")
    @classmethod
    def normalize_optional_contact_text(cls, value: object) -> object:
        if isinstance(value, str):
            clean = value.strip()
            return clean or None
        return value

    @field_validator("phone")
    @classmethod
    def validate_contact_phone(cls, value: str) -> str:
        digits = re.sub(r"[^0-9]", "", value)
        if not re.fullmatch(r"\+?[0-9()\-\s]+", value) or not 10 <= len(digits) <= 15:
            raise ValueError("Enter 10–15 phone digits with an optional country code")
        return value


class ContactInquiryAdmin(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str
    company_name: str | None
    subject: str | None
    message: str
    inquiry_type: str
    status: str
    notes: str | None
    created_at: str
    updated_at: str


class ContactInquiryUpdate(BaseModel):
    status: str = Field(max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
