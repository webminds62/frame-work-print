create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  created_at timestamptz not null default now()
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  merchant_reference text not null unique,
  prodigi_order_id text unique,
  prodigi_sku text not null,
  status text not null default 'received',
  prodigi_stage text,
  tracking_url text,
  amount numeric(10,2),
  currency text not null default 'USD',
  recipient jsonb not null,
  asset_url text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.orders enable row level security;

create policy "users read own profile" on public.profiles for select using (auth.uid() = id);
create policy "users read own orders" on public.orders for select using (auth.uid() = user_id);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

create or replace trigger on_auth_user_created
after insert on auth.users for each row execute procedure public.handle_new_user();
