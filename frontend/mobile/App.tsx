import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { Provider as PaperProvider, MD3LightTheme, configureFonts } from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';

import HomeScreen from './src/screens/HomeScreen';
import AnalysisScreen from './src/screens/AnalysisScreen';
import TestScreen from './src/screens/TestScreen';
import { RootStackParamList } from './src/types';

const Stack = createStackNavigator<RootStackParamList>();

// Custom theme colors
const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#1976d2',
    secondary: '#26a69a',
    tertiary: '#ff9800',
    surface: '#ffffff',
    background: '#f5f5f5',
    error: '#f44336',
    onPrimary: '#ffffff',
    onSecondary: '#ffffff',
    onSurface: '#000000',
    onBackground: '#000000',
  },
};

export default function App() {
  return (
    <PaperProvider theme={theme}>
      <NavigationContainer>
        <StatusBar style="auto" />
        <Stack.Navigator
          initialRouteName="Home"
          screenOptions={{
            headerStyle: {
              backgroundColor: '#1976d2',
            },
            headerTintColor: '#fff',
            headerTitleStyle: {
              fontWeight: 'bold',
            },
          }}
        >
          <Stack.Screen
            name="Test"
            component={TestScreen}
            options={{ title: '🧪 System Test' }}
          />
          <Stack.Screen
            name="Home"
            component={HomeScreen}
            options={{ title: 'StockBuddy' }}
          />
          <Stack.Screen
            name="Analysis"
            component={AnalysisScreen}
            options={{ title: 'Analysis Result' }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </PaperProvider>
  );
}
