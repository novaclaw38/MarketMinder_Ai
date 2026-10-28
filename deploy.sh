#!/bin/bash
# Deploy MarketMinder AI to Vercel
# Usage: ./deploy.sh [preview|production]

set -e

echo "🚀 Deploying MarketMinder AI to Vercel..."

# Check vercel CLI
if ! command -v vercel &> /dev/null; then
    echo "Installing Vercel CLI..."
    npm install -g vercel
fi

# Install dependencies
echo "Installing dependencies..."
npm install

# Check if we're in a Vercel project already
if [ ! -f .vercel/project.json ]; then
    echo "Linking to Vercel project..."
    vercel link --yes
fi

# Set environment variables (you'll need to set these in Vercel Dashboard)
echo ""
echo "⚠️  IMPORTANT: Set these environment variables in Vercel Dashboard:"
echo "   - NEXT_PUBLIC_SUPABASE_URL"
echo "   - NEXT_PUBLIC_SUPABASE_ANON_KEY"
echo "   - SUPABASE_SERVICE_ROLE_KEY"
echo ""
echo "Run this command to set them:"
echo "   vercel env add NEXT_PUBLIC_SUPABASE_URL <url> <scope>"
echo "   vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY <key> <scope>"
echo "   vercel env add SUPABASE_SERVICE_ROLE_KEY <key> <scope>"
echo ""

read -p "Press enter after setting env vars, or Ctrl+C to abort..."

# Deploy!
ENV_TYPE=${1:-preview}

if [ "$ENV_TYPE" == "production" ]; then
    echo "Deploying to production..."
    vercel --prod
else
    echo "Deploying preview..."
    vercel
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Set up Supabase database (see VERCEL_DEPLOY.md)"
echo "2. Configure custom domain in Vercel (optional)"
echo "3. Set up cron jobs for agent orchestration (see docs/cron-setup.md)"