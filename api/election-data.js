// Vercel Serverless Function
// Deploy this to Vercel to create a secure API endpoint

export default async function handler(req, res) {
  // Enable CORS for your website
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  
  try {
    const response = await fetch(
      `https://api.github.com/repos/${process.env.GITHUB_USER}/${process.env.GITHUB_REPO}/contents/seat.json`,
      {
        headers: {
          'Authorization': `token ${process.env.GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3.raw'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to fetch data');
    }
    
    const data = await response.json();
    
    // Return the data
    res.status(200).json(data);
    
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch election data' });
  }
}
