import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, Alert } from 'react-native';
import { Button, Card, Title, Text, Divider } from 'react-native-paper';
import { API_BASE_URL } from '../config/api';

export default function TestScreen() {
  const [result, setResult] = useState('');

  const testBasicClick = () => {
    console.log('✅ Basic click test successful');
    alert('✅ Basic click working!');
    setResult('Basic Click: ✅ Success');
  };

  const testAPIConfig = () => {
    console.log('📡 API Base URL:', API_BASE_URL);
    alert(`API URL: ${API_BASE_URL}`);
    setResult(`API URL: ${API_BASE_URL}`);
  };

  const testFetch = async () => {
    console.log('🔍 Testing API connection...');
    setResult('Testing...');
    
    const urls = [
      { name: 'localhost', url: 'http://localhost:8000/api/health' },
      { name: 'LAN IP', url: 'http://172.27.183.237:8000/api/health' },
      { name: 'Current Config', url: `${API_BASE_URL}/api/health` },
    ];
    
    let results = `API_BASE_URL = ${API_BASE_URL}\n\n`;
    
    for (const { name, url } of urls) {
      try {
        console.log(`Testing ${name}: ${url}`);
        const startTime = Date.now();
        const response = await fetch(url, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
        });
        const duration = Date.now() - startTime;
        const data = await response.json();
        results += `✅ ${name}\n   ${duration}ms | Status: ${response.status}\n\n`;
        console.log(`${name} Success:`, data);
      } catch (error: any) {
        results += `❌ ${name}\n   Error: ${error.message}\n\n`;
        console.error(`${name} Failed:`, error);
      }
    }
    
    setResult(results);
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Card style={styles.card}>
          <Card.Content>
            <Title>🧪 System Test</Title>
            <Divider style={styles.divider} />
            
            <Button 
              mode="contained" 
              onPress={testBasicClick}
              style={styles.button}
            >
              1️⃣ Test Basic Click
            </Button>

            <Button 
              mode="contained" 
              onPress={testAPIConfig}
              style={styles.button}
            >
              2️⃣ View API Config
            </Button>

            <Button 
              mode="contained" 
              onPress={testFetch}
              style={styles.button}
            >
              3️⃣ Test API Connection
            </Button>

            {result && (
              <>
                <Divider style={styles.divider} />
                <Text style={styles.result}>{result}</Text>
              </>
            )}
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Title>📋 Checklist</Title>
            <Divider style={styles.divider} />
            <Text>1. Open browser console (F12)</Text>
            <Text>2. Click the test buttons above</Text>
            <Text>3. Check console output</Text>
            <Text>4. Check alert messages</Text>
          </Card.Content>
        </Card>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  content: {
    padding: 16,
  },
  card: {
    marginBottom: 16,
  },
  button: {
    marginVertical: 8,
  },
  divider: {
    marginVertical: 12,
  },
  result: {
    marginTop: 8,
    padding: 12,
    backgroundColor: '#e8f4fd',
    borderRadius: 4,
    fontFamily: 'monospace',
  },
});
