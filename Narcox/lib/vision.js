async function analyzeImage(imageUrl) {
  // Use the new AWS Custom Vision Microservice!
  const AWS_SERVER_IP = "54.221.93.68"; 
  const AWS_API_URL = `http://${AWS_SERVER_IP}:8000/analyze`;

  try {
    const response = await fetch(AWS_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_url: imageUrl })
    });

    if (!response.ok) {
      throw new Error(`AWS Server returned ${response.status}`);
    }

    const data = await response.json();
    
    // The AWS server returns { top_label: "...", risk: 10/0 }
    return {
      labels: [data.top_label],
      risk: data.risk
    };

  } catch (error) {
    console.error('AWS Vision API Error:', error.message);
    // Silent fail for hackathon demo if AWS crashes
    return { labels: [`AWS Error: ${error.message}`], risk: 0 };
  }
}

module.exports = { analyzeImage };
