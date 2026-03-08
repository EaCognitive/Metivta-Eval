# Supabase Setup Guide for Metivta Eval

## 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Sign in with your GitHub account
3. Click "New Project"
4. Fill in:
   - Project Name: `metivta-eval`
   - Database Password: (generate a strong password)
   - Region: `US East (N. Virginia)`
   - Plan: Free tier ($0/month)
5. Click "Create new project"
6. Wait for project to initialize (~2 minutes)

## 2. Set Up Database Tables

1. In your Supabase dashboard, go to **SQL Editor**
2. Click "New Query"
3. Copy and paste the entire contents of `supabase_schema.sql`
4. Click "Run" to execute the SQL
5. You should see "Success. No rows returned"

## 3. Get Your API Credentials

1. Go to **Settings** → **API** in your Supabase dashboard
2. Copy these values:
   - **Project URL**: `https://[your-project-id].supabase.co`
   - **Anon/Public Key**: `eyJ...` (long string)

## 4. Configure Environment Variables

### For Local Development

Add to your `.env` file:
```bash
SUPABASE_URL=https://[your-project-id].supabase.co
SUPABASE_ANON_KEY=eyJ...your-anon-key...
```

### For Render Deployment

1. Go to your Render service dashboard
2. Click on **Environment** tab
3. Add these environment variables:
   - `SUPABASE_URL` = Your Project URL
   - `SUPABASE_ANON_KEY` = Your Anon Key

## 5. Test the Connection

Once configured, the application will automatically:
- Connect to Supabase on startup
- Create tables if they don't exist
- Use the test API key for development

## 6. API Key Management

The default test API key for development:
```
mtv_test_development_key_2024
```

To create new API keys, use the `/api/create-key` endpoint or insert directly into the `api_keys` table.

## 7. Monitoring

- View data in **Table Editor** in Supabase dashboard
- Check logs in **Logs** section
- Monitor usage in **Reports** section

## Troubleshooting

### Connection Issues
- Ensure environment variables are set correctly
- Check that tables were created successfully
- Verify Row Level Security policies are in place

### Permission Errors
- Make sure you're using the anon key, not the service key
- Check RLS policies in the SQL Editor

### Data Not Appearing
- Verify insertions are successful in the logs
- Check the Table Editor to see raw data
- Ensure RLS policies allow the operations you need