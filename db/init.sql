CREATE TABLE accounts (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    status      VARCHAR(10) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE payments (
    id              SERIAL PRIMARY KEY,
    amount          NUMERIC(15,2) NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    debit_account   INTEGER NOT NULL REFERENCES accounts(id),
    credit_account  INTEGER NOT NULL REFERENCES accounts(id),
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- Seed data
INSERT INTO accounts (name, account_type, status) VALUES
    ('Alice Savings',   'savings',  'active'),
    ('Bob Current',     'current',  'active'),
    ('Charlie Business','business', 'active');

INSERT INTO payments (amount, currency, debit_account, credit_account) VALUES
    (250.00, 'USD', 1, 2),
    (100.50, 'EUR', 2, 3);
