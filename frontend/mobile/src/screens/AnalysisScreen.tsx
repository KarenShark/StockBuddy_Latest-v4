import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Alert,
} from 'react-native';
import {
  Card,
  Title,
  Paragraph,
  ProgressBar,
  ActivityIndicator,
  Button,
  Text,
  Divider,
  Chip,
} from 'react-native-paper';
import { StackNavigationProp } from '@react-navigation/stack';
import { RouteProp } from '@react-navigation/native';
import { RootStackParamList, TaskStatus } from '../types';
import { tradingApi } from '../services/api';

type AnalysisScreenNavigationProp = StackNavigationProp<
  RootStackParamList,
  'Analysis'
>;
type AnalysisScreenRouteProp = RouteProp<RootStackParamList, 'Analysis'>;

interface Props {
  navigation: AnalysisScreenNavigationProp;
  route: AnalysisScreenRouteProp;
}

export default function AnalysisScreen({ navigation, route }: Props) {
  const { taskId, ticker } = route.params;
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTaskStatus = async () => {
    try {
      const status = await tradingApi.getTaskStatus(taskId);
      setTaskStatus(status);
      setLoading(false);
      setRefreshing(false);

      // If task is still running, continue polling
      if (status.status === 'running' || status.status === 'pending') {
        setTimeout(fetchTaskStatus, 3000); // Poll every 3 seconds
      }
    } catch (error: any) {
      console.error('Failed to get status:', error);
      setLoading(false);
      setRefreshing(false);
      Alert.alert('Error', 'Failed to get analysis status');
    }
  };

  useEffect(() => {
    fetchTaskStatus();
  }, [taskId]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchTaskStatus();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#4caf50';
      case 'running':
        return '#2196f3';
      case 'pending':
        return '#ff9800';
      case 'error':
        return '#f44336';
      default:
        return '#9e9e9e';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed':
        return '✅ Analysis Complete';
      case 'running':
        return '🔄 Analyzing...';
      case 'pending':
        return '⏳ Pending...';
      case 'error':
        return '❌ Analysis Failed';
      default:
        return status;
    }
  };

  if (loading && !taskStatus) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>Getting analysis status...</Text>
      </View>
    );
  }

  const progress = taskStatus?.progress?.percentage || 0;
  const isCompleted = taskStatus?.status === 'completed';
  const isError = taskStatus?.status === 'error';

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Card style={styles.card}>
        <Card.Content>
          <Title style={styles.ticker}>{ticker}</Title>
          <Chip
            mode="outlined"
            style={[
              styles.statusChip,
              { borderColor: getStatusColor(taskStatus?.status || '') },
            ]}
            textStyle={{ color: getStatusColor(taskStatus?.status || '') }}
          >
            {getStatusText(taskStatus?.status || '')}
          </Chip>
        </Card.Content>
      </Card>

      {!isCompleted && !isError && (
        <Card style={styles.card}>
          <Card.Content>
            <Title style={styles.sectionTitle}>Analysis Progress</Title>
            <ProgressBar progress={progress / 100} style={styles.progressBar} />
            <Text style={styles.progressText}>{progress}%</Text>
            {taskStatus?.progress?.current_agent && (
              <Paragraph style={styles.currentAgent}>
                Current: {taskStatus.progress.current_agent}
              </Paragraph>
            )}
          </Card.Content>
        </Card>
      )}

      {isError && (
        <Card style={[styles.card, styles.errorCard]}>
          <Card.Content>
            <Title style={styles.errorTitle}>❌ Analysis Failed</Title>
            <Paragraph>{taskStatus?.error || 'Unknown error'}</Paragraph>
            <Button
              mode="contained"
              onPress={() => navigation.goBack()}
              style={styles.button}
            >
              Go Back & Retry
            </Button>
          </Card.Content>
        </Card>
      )}

      {isCompleted && taskStatus?.result && (
        <>
          <Card style={styles.card}>
            <Card.Content>
              <Title style={styles.sectionTitle}>💡 Final Decision</Title>
              <Divider style={styles.divider} />
              <Paragraph style={styles.decision}>
                {taskStatus.result.decision || 'No decision info'}
              </Paragraph>
            </Card.Content>
          </Card>

          {taskStatus.result.market_report && (
            <Card style={styles.card}>
              <Card.Content>
                <Title style={styles.sectionTitle}>📊 Market Analysis</Title>
                <Divider style={styles.divider} />
                <Paragraph>{taskStatus.result.market_report}</Paragraph>
              </Card.Content>
            </Card>
          )}

          {taskStatus.result.sentiment_report && (
            <Card style={styles.card}>
              <Card.Content>
                <Title style={styles.sectionTitle}>💬 Social Sentiment</Title>
                <Divider style={styles.divider} />
                <Paragraph>{taskStatus.result.sentiment_report}</Paragraph>
              </Card.Content>
            </Card>
          )}

          {taskStatus.result.news_report && (
            <Card style={styles.card}>
              <Card.Content>
                <Title style={styles.sectionTitle}>📰 News Analysis</Title>
                <Divider style={styles.divider} />
                <Paragraph>{taskStatus.result.news_report}</Paragraph>
              </Card.Content>
            </Card>
          )}

          {taskStatus.result.fundamentals_report && (
            <Card style={styles.card}>
              <Card.Content>
                <Title style={styles.sectionTitle}>💰 Fundamentals</Title>
                <Divider style={styles.divider} />
                <Paragraph>{taskStatus.result.fundamentals_report}</Paragraph>
              </Card.Content>
            </Card>
          )}

          {taskStatus.result.final_trade_decision && (
            <Card style={styles.card}>
              <Card.Content>
                <Title style={styles.sectionTitle}>📋 Final Trade Decision</Title>
                <Divider style={styles.divider} />
                <Paragraph>{taskStatus.result.final_trade_decision}</Paragraph>
              </Card.Content>
            </Card>
          )}

          <Button
            mode="outlined"
            onPress={() => navigation.goBack()}
            style={styles.button}
          >
            Back to Home
          </Button>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  ticker: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1976d2',
    textAlign: 'center',
  },
  statusChip: {
    alignSelf: 'center',
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 18,
    marginBottom: 8,
  },
  progressBar: {
    height: 10,
    borderRadius: 5,
  },
  progressText: {
    textAlign: 'center',
    marginTop: 8,
    fontSize: 16,
    fontWeight: 'bold',
  },
  currentAgent: {
    textAlign: 'center',
    marginTop: 8,
    fontStyle: 'italic',
    color: '#666',
  },
  decision: {
    fontSize: 16,
    lineHeight: 24,
    fontWeight: 'bold',
    color: '#1976d2',
  },
  divider: {
    marginVertical: 8,
  },
  errorCard: {
    backgroundColor: '#ffebee',
  },
  errorTitle: {
    color: '#f44336',
  },
  button: {
    marginTop: 16,
  },
});
