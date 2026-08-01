import React from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

import FeatureCard from '../components/FeatureCard';
import { API_BASE_URL } from '../config/api';

const featureCards = [
  {
    title: 'Shared backend connection',
    description: 'The native app is prepared to call the same FastAPI backend used by the web app.',
  },
  {
    title: 'Inventory and client workflows',
    description: 'The folder structure is ready for native screens covering stock, clients, payments, and team activity.',
  },
  {
    title: 'Future iPhone rollout',
    description: 'Use Expo Go first, then move to a development build or TestFlight when native features are added.',
  },
];

export default function HomeScreen() {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.hero}>
          <Text style={styles.eyebrow}>Native iPhone app scaffold</Text>
          <Text style={styles.title}>Woodful Creations Mobile</Text>
          <Text style={styles.subtitle}>
            This Expo app is intentionally small so the repository is ready for native iPhone work
            later without affecting the current laptop web flow.
          </Text>
        </View>

        <View style={styles.panel}>
          <Text style={styles.panelTitle}>API base URL</Text>
          <Text style={styles.panelValue}>{API_BASE_URL}</Text>
          <Text style={styles.panelHelper}>
            When running on an iPhone, replace localhost with your computer's LAN IP in
            mobile/.env.
          </Text>
        </View>

        {featureCards.map((card) => (
          <FeatureCard key={card.title} title={card.title} description={card.description} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#f6f1ea',
  },
  container: {
    padding: 24,
  },
  hero: {
    marginBottom: 24,
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: '#8a5c36',
    marginBottom: 10,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: '#1f2937',
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 15,
    lineHeight: 24,
    color: '#52606d',
  },
  panel: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    padding: 20,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  panelTitle: {
    fontSize: 13,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    color: '#8a5c36',
    marginBottom: 8,
  },
  panelValue: {
    fontSize: 16,
    color: '#243b53',
    marginBottom: 8,
  },
  panelHelper: {
    fontSize: 14,
    lineHeight: 21,
    color: '#52606d',
  },
});
