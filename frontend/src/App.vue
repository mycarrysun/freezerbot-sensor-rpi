<template>
  <div class="container">
    <div class="logo">
      <img src="/logo.svg" alt="Freezerbot Logo">
    </div>
    <h1>Setup Your Sensor</h1>

    <AccountCheck v-if="step === 'account'" @continue-to-setup="step = 'setup'"/>
    <SetupForm v-if="step === 'setup'" @setup-completed="onSetupCompleted" />

    <div v-if="step === 'complete'" class="success">
      <div class="success-icon">✓</div>
      <h2>Setup Complete!</h2>
      <p>Your sensor has been successfully configured and will switch to monitoring mode in:</p>
      <div class="countdown">{{ countdown }}</div>
      <p>You can now close this page and go back to the Freezerbot Sensors list to view your new Sensor</p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import SetupForm from './components/SetupForm.vue';
import AccountCheck from '@/components/AccountCheck.vue'

const countdown = ref(10);
const step = ref<'account' | 'setup' | 'complete'>('account');

function onSetupCompleted() {
  step.value = 'complete';
  const timer = setInterval(() => {
    countdown.value--;

    if (countdown.value <= 0) {
      clearInterval(timer);
    }
  }, 1000);
}
</script>

<style lang="scss">
@import './css/app.css';

.container {
  max-width: 500px;
  margin: 0 auto;
  background: var(--card-color);
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.logo {
  text-align: center;
  margin-bottom: 20px;
}
.logo img {
  width: 180px;
}
h1 {
  text-align: center;
  color: var(--primary-color);
  font-weight: 700;
}
.success {
  text-align: center;

  a {
    display: inline-flex;
    margin: 1rem;
  }
}
.success-icon {
  font-size: 60px;
  color: #4CAF50;
  margin-bottom: 20px;
}
.countdown {
  font-size: 24px;
  margin: 20px 0;
  font-weight: bold;
}
</style>