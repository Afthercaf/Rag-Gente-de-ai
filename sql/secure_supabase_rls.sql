-- Ejecutar únicamente después de configurar el backend con una
-- SUPABASE_SERVICE_ROLE_KEY / sb_secret_... mantenida fuera del frontend.
-- Esta migración corta todo acceso REST directo de anon/authenticated.

begin;

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'users',
        'ordenes',
        'orders',
        'chat_history',
        'promociones'
    ]
    loop
        if to_regclass('public.' || quote_ident(table_name)) is not null then
            execute format(
                'alter table public.%I enable row level security',
                table_name
            );
            execute format(
                'alter table public.%I force row level security',
                table_name
            );
            execute format(
                'revoke all privileges on table public.%I from anon, authenticated',
                table_name
            );
            execute format(
                'grant select, insert, update, delete on table public.%I to service_role',
                table_name
            );
        end if;
    end loop;
end
$$;

commit;
