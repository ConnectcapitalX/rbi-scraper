const { MongoClient } = require('mongodb');

const uri = 'mongodb+srv://connectcapitalx:Growth%402025%21@cluster0.znc9sah.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0';
const dbName = 'rbi';

async function testConnection() {
  const client = new MongoClient(uri);
  try {
    await client.connect();
    const db = client.db(dbName);
    const collections = await db.listCollections().toArray();
    console.log('Connected! Collections:', collections.map(c => c.name));
  } catch (err) {
    console.error('MongoDB connection error:', err);
  } finally {
    await client.close();
  }
}

testConnection();