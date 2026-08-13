-- =====================================================================
-- 0068 — AI EMPLOYEE DEFAULT MODEL
-- Deployments configured with a Google Gemini key (GOOGLE_AI_KEY) have no
-- OPENAI_API_KEY, so AI employees seeded with 'gpt-5' fail every chat turn
-- with "OPENAI_API_KEY is not configured" (the router treats missing keys as
-- fatal, by design). Repoint existing rows to the deployment's model and
-- normalize the seed helper so new orgs get a usable model too.
-- =====================================================================

UPDATE public.ai_employees
SET model = 'gemini-3.5-flash'
WHERE model = 'gpt-5';

-- Normalize inside the seed helper: any caller passing the legacy 'gpt-5'
-- model (the 0060 seed body, older org-creation triggers, etc.) transparently
-- gets the deployment model instead.
CREATE OR REPLACE FUNCTION public._seed_ai_employee(
    p_org_id UUID, p_name TEXT, p_role TEXT, p_desc TEXT,
    p_model TEXT, p_tools JSONB, p_permissions JSONB
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    p_model := CASE WHEN p_model = 'gpt-5' THEN 'gemini-3.5-flash' ELSE p_model END;
    INSERT INTO public.ai_employees
        (organization_id, name, role, description, model, tools, permissions, active)
    VALUES
        (p_org_id, p_name, p_role, p_desc, p_model, p_tools, p_permissions, TRUE)
    ON CONFLICT (organization_id, name) DO NOTHING;
END;
$$;
