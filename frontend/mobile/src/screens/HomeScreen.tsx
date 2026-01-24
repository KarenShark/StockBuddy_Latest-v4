import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import {
  TextInput,
  Button,
  Card,
  Title,
  Paragraph,
  Chip,
  ActivityIndicator,
  Text,
  Divider,
} from 'react-native-paper';
import { StackNavigationProp } from '@react-navigation/stack';
import { RootStackParamList } from '../types';
import { tradingApi } from '../services/api';
import { API_BASE_URL } from '../config/api';

type HomeScreenNavigationProp = StackNavigationProp<RootStackParamList, 'Home'>;

interface Props {
  navigation: HomeScreenNavigationProp;
}

export default function HomeScreen({ navigation }: Props) {
  const [ticker, setTicker] = useState('AAPL');
  const [loading, setLoading] = useState(false);
  const [selectedAnalysts, setSelectedAnalysts] = useState([
    'market',
    'social',
    'news',
    'fundamentals',
  ]);

  // Print debug info when component loads
  React.useEffect(() => {
    console.log('🏠 HomeScreen component loaded');
    console.log('📡 API config:', API_BASE_URL);
  }, []);

  const analysts = [
    { key: 'market', label: 'Market Analysis' },
    { key: 'social', label: 'Social Media' },
    { key: 'news', label: 'News Analysis' },
    { key: 'fundamentals', label: 'Fundamentals' },
  ];

  const toggleAnalyst = (analystKey: string) => {
    if (selectedAnalysts.includes(analystKey)) {
      setSelectedAnalysts(selectedAnalysts.filter((a) => a !== analystKey));
    } else {
      setSelectedAnalysts([...selectedAnalysts, analystKey]);
    }
  };

  const handleAnalyze = async () => {
    console.log('🔍 Start analysis button clicked');
    console.log('📊 Stock ticker:', ticker);
    console.log('👥 Selected analysts:', selectedAnalysts);
    
    if (!ticker.trim()) {
      console.log('❌ Stock ticker is empty');
      Alert.alert('Error', 'Please enter a stock ticker');
      return;
    }

    if (selectedAnalysts.length === 0) {
      console.log('❌ No analysts selected');
      Alert.alert('Error', 'Please select at least one analyst');
      return;
    }

    setLoading(true);
    console.log('⏳ Starting API connection...');

    try {
      // Test connection
      console.log('🔗 Testing API connection...');
      const healthResponse = await tradingApi.healthCheck();
      console.log('✅ API connection successful:', healthResponse);

      // Create analysis task
      console.log('📤 Creating analysis task...');
      const response = await tradingApi.createAnalysis({
        ticker: ticker.toUpperCase(),
        analysts: selectedAnalysts,
        research_depth: 1,
      });
      console.log('✅ Task created successfully:', response);

      setLoading(false);

      // Navigate to analysis result page
      console.log('🔄 Navigating to analysis page...');
      navigation.navigate('Analysis', {
        taskId: response.task_id,
        ticker: ticker.toUpperCase(),
      });
    } catch (error: any) {
      setLoading(false);
      console.error('❌ Analysis error:', error);
      console.error('Error details:', JSON.stringify(error, null, 2));
      
      if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
        Alert.alert(
          'Connection Failed',
          'Cannot connect to server.\n\nPlease ensure:\n1. FastAPI server is running (http://localhost:8000)\n2. API_BASE_URL is configured correctly\n\nCurrent config: http://172.27.183.237:8000'
        );
      } else {
        Alert.alert('Error', error.message || 'Analysis failed, please try again');
      }
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView 
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={true}
      >
        <Card style={styles.card}>
          <Card.Content>
            <Title style={styles.title}>StockBuddy</Title>
            <Paragraph style={styles.subtitle}>
              AI Multi-Agent Trading Analysis System
            </Paragraph>
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Title style={styles.sectionTitle}>Stock Ticker</Title>
            <TextInput
              label="Enter ticker (e.g., AAPL, NVDA)"
              value={ticker}
              onChangeText={setTicker}
              mode="outlined"
              autoCapitalize="characters"
              style={styles.input}
            />
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Title style={styles.sectionTitle}>Select Analysts</Title>
            <View style={styles.chipsContainer}>
              {analysts.map((analyst) => (
                <Chip
                  key={analyst.key}
                  selected={selectedAnalysts.includes(analyst.key)}
                  onPress={() => toggleAnalyst(analyst.key)}
                  style={styles.chip}
                  mode="outlined"
                >
                  {analyst.label}
                </Chip>
              ))}
            </View>
          </Card.Content>
        </Card>

        <Button
          mode="contained"
          onPress={() => {
            console.log('🔥 Button clicked!');
            alert('Button click test successful!');
            handleAnalyze();
          }}
          loading={loading}
          disabled={loading}
          style={styles.button}
          contentStyle={styles.buttonContent}
          buttonColor="#1976d2"
          textColor="#ffffff"
        >
          {loading ? 'Creating analysis task...' : '🚀 Start Analysis'}
        </Button>
        
        <Button
          mode="outlined"
          onPress={() => {
            console.log('✅ Test button working');
            alert('If you see this, button events are working properly!');
          }}
          style={styles.button}
        >
          🧪 Test Button
        </Button>

        <Card style={[styles.card, styles.infoCard]}>
          <Card.Content>
            <Title style={styles.infoTitle}>💡 Tips</Title>
            <Divider style={styles.divider} />
            <Paragraph style={styles.infoParagraph}>
              Enter stock ticker (e.g., AAPL, NVDA){'\n'}
              Select the analyst types you need{'\n'}
              Click Start Analysis to get AI analysis report
            </Paragraph>
          </Card.Content>
        </Card>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 50,
    flexGrow: 1,
  },
  card: {
    marginBottom: 16,
    elevation: 4,
    backgroundColor: '#ffffff',
    borderRadius: 12,
  },
  title: {
    fontSize: 34,
    fontWeight: 'bold',
    textAlign: 'center',
    color: '#1976d2',
    marginTop: 12,
    marginBottom: 4,
  },
  subtitle: {
    textAlign: 'center',
    color: '#666',
    marginTop: 4,
    fontSize: 15,
  },
  sectionTitle: {
    fontSize: 20,
    marginBottom: 12,
    fontWeight: '600',
    color: '#333',
  },
  input: {
    backgroundColor: '#f8f9fa',
  },
  chipsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  chip: {
    marginBottom: 10,
    marginRight: 8,
  },
  button: {
    marginVertical: 20,
    borderRadius: 8,
  },
  buttonContent: {
    paddingVertical: 12,
  },
  infoCard: {
    backgroundColor: '#e8f4fd',
    borderLeftWidth: 4,
    borderLeftColor: '#1976d2',
  },
  infoTitle: {
    fontSize: 20,
    color: '#1976d2',
    fontWeight: '600',
  },
  divider: {
    marginVertical: 10,
    backgroundColor: '#1976d2',
    height: 2,
  },
  infoParagraph: {
    lineHeight: 26,
    color: '#424242',
    fontSize: 15,
  },
});
