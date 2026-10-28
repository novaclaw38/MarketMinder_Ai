import Node from 'next/dist/server/node-server'

// Export config for Vercel
export const config = {
  api: {
    bodyParser: false,
  },
}

// Server handler
export default async function handler(req: any, res: any) {
  if (req.method === 'GET') {
    res.status(200).json({
      status: 'ok',
      message: 'MarketMinder AI API is running',
      timestamp: new Date().toISOString()
    })
  } else {
    res.status(405).json({ error: 'Method not allowed' })
  }
}