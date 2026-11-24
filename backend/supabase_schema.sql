-- ==============================================================================
-- ENERTECH PLATFORM - COMPLETE SUPABASE PRODUCTION DATABASE SCHEMA
-- Target Database: PostgreSQL 15+ / Supabase
-- Paste this in: Supabase Dashboard -> SQL Editor -> New Query -> Run
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. ADMIN ACCOUNTS (Role-based access control for CMS)
CREATE TABLE IF NOT EXISTS admin_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(254),
    display_name VARCHAR(180),
    role VARCHAR(32) NOT NULL DEFAULT 'content_editor', -- 'super_admin', 'admin', 'content_editor'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admin_accounts_uid ON admin_accounts(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_admin_accounts_role ON admin_accounts(role);

-- 2. APP CONFIG (Staged & Published content for mobile app sections)
CREATE TABLE IF NOT EXISTS app_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(80) UNIQUE NOT NULL, -- 'home', 'contacts', 'solution_finder', 'chat', 'brand'
    draft_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    published_payload JSONB,
    draft_revision INTEGER NOT NULL DEFAULT 1,
    published_revision INTEGER,
    updated_by VARCHAR(128),
    published_by VARCHAR(128),
    published_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_app_config_key ON app_config(key);

-- 3. AUDIT EVENTS (Change tracking and compliance)
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_uid VARCHAR(128) NOT NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id VARCHAR(160) NOT NULL,
    change_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events(actor_uid);
CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC);

-- 4. CUSTOMER PROFILES (Users, Resellers, EPC, Distributors with GST and Company)
CREATE TABLE IF NOT EXISTS customer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(128) UNIQUE NOT NULL,
    customer_type VARCHAR(24) NOT NULL, -- 'end_user', 'reseller', 'epc', 'distributor'
    name VARCHAR(180) NOT NULL,
    mobile_number VARCHAR(24) NOT NULL,
    email VARCHAR(254) NOT NULL,
    location VARCHAR(500) NOT NULL,
    company_name VARCHAR(220),          -- Required for reseller, epc, distributor
    gst_number VARCHAR(32),             -- Required 15-char GST for business tiers
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_uid ON customer_profiles(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_type ON customer_profiles(customer_type);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_email ON customer_profiles(email);

-- 5. CUSTOMER REQUESTS (Service Requests, Quote Requests, Enquiries)
CREATE TABLE IF NOT EXISTS customer_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_uid VARCHAR(128) NOT NULL,
    customer_email VARCHAR(254) NOT NULL,
    kind VARCHAR(32) NOT NULL, -- 'service', 'quote', 'inquiry'
    status VARCHAR(40) NOT NULL DEFAULT 'submitted', -- 'submitted', 'in_review', 'assigned', 'resolved', 'closed', etc.
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,      -- stores model, serial, issue, load_kwh, etc.
    assigned_to VARCHAR(128),
    resolution_note VARCHAR(2000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customer_requests_uid ON customer_requests(customer_uid);
CREATE INDEX IF NOT EXISTS idx_customer_requests_kind ON customer_requests(kind);
CREATE INDEX IF NOT EXISTS idx_customer_requests_status ON customer_requests(status);
CREATE INDEX IF NOT EXISTS idx_customer_requests_created ON customer_requests(created_at DESC);

-- 6. CONTACT INQUIRIES & LEADS (Website & App Contact Form Submissions)
CREATE TABLE IF NOT EXISTS contact_inquiries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(180) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(24) NOT NULL,
    company_name VARCHAR(220),
    subject VARCHAR(220),
    message TEXT NOT NULL,
    inquiry_type VARCHAR(50) NOT NULL DEFAULT 'general', -- 'general', 'dealership', 'support', 'sales', 'epc'
    status VARCHAR(40) NOT NULL DEFAULT 'new',           -- 'new', 'in_progress', 'contacted', 'closed'
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_inquiries_email ON contact_inquiries(email);
CREATE INDEX IF NOT EXISTS idx_contact_inquiries_status ON contact_inquiries(status);
CREATE INDEX IF NOT EXISTS idx_contact_inquiries_type ON contact_inquiries(inquiry_type);
CREATE INDEX IF NOT EXISTS idx_contact_inquiries_created ON contact_inquiries(created_at DESC);

-- 7. KNOWLEDGE BASE ARTICLES (FAQs & Support Knowledge)
CREATE TABLE IF NOT EXISTS knowledge_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(180) UNIQUE NOT NULL,
    title VARCHAR(220) NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'General',
    answer TEXT NOT NULL,
    source_reference VARCHAR(1000),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    draft_data JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_articles_slug ON knowledge_articles(slug);
CREATE INDEX IF NOT EXISTS idx_knowledge_articles_cat ON knowledge_articles(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_articles_pub ON knowledge_articles(is_published);

-- 8. PRODUCT CATEGORIES (WooCommerce & CMS Catalogue Categories)
CREATE TABLE IF NOT EXISTS product_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(180) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    image_url VARCHAR(1000),
    wordpress_source_id VARCHAR(64) UNIQUE,
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    draft_data JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_categories_slug ON product_categories(slug);
CREATE INDEX IF NOT EXISTS idx_product_categories_wp_id ON product_categories(wordpress_source_id);
CREATE INDEX IF NOT EXISTS idx_product_categories_pub ON product_categories(is_published);

-- 9. PRODUCTS (Inverters, Online UPS, Batteries, Solar Solutions)
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES product_categories(id) ON DELETE SET NULL,
    slug VARCHAR(180) UNIQUE NOT NULL,
    name VARCHAR(240) NOT NULL,
    model_code VARCHAR(80),
    summary TEXT,
    description TEXT,
    applications JSONB NOT NULL DEFAULT '[]'::jsonb,
    features JSONB NOT NULL DEFAULT '[]'::jsonb,
    specifications JSONB NOT NULL DEFAULT '{}'::jsonb,
    image_url VARCHAR(1000),
    gallery_images JSONB NOT NULL DEFAULT '[]'::jsonb,
    price_minor BIGINT,
    currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
    currency_minor_unit SMALLINT NOT NULL DEFAULT 2,
    stock_status VARCHAR(20) NOT NULL DEFAULT 'instock', -- 'instock', 'outofstock', 'onbackorder'
    stock_quantity INTEGER,
    documents JSONB NOT NULL DEFAULT '[]'::jsonb,
    wordpress_source_id VARCHAR(64) UNIQUE,
    wordpress_source_url VARCHAR(1000),
    source_reference VARCHAR(1000),
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    draft_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_wp_id ON products(wordpress_source_id);
CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock_status);
CREATE INDEX IF NOT EXISTS idx_products_pub ON products(is_published);

-- 10. CRITICAL PERMISSIONS & ROLE GRANTS FOR POSTGREST & FASTAPI
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON ROUTINES TO postgres, anon, authenticated, service_role;
