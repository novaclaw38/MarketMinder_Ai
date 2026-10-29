import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  const site = (process.env.SITE_URL || '').replace(/\/$/, '')
  return {
    rules: { userAgent: '*', allow: ['/p/', '/blog/'], disallow: ['/api/', '/dashboard', '/login'] },
    ...(site ? { sitemap: `${site}/sitemap.xml` } : {})
  }
}
