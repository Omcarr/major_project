/** @jsxImportSource theme-ui */
import React, { useEffect, useState, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { Box, Heading, Text } from 'theme-ui'

const MAX_DATA_POINTS = 200

function App() {
  const [data, setData] = useState([])
  const ws = useRef(null)

  useEffect(() => {
    ws.current = new WebSocket('ws://YOUR_PC_IP:8765') // Replace with your WebSocket server IP

    ws.current.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.current.onmessage = (event) => {
      const eegValue = parseFloat(event.data)
      if (!isNaN(eegValue)) {
        setData((prev) => {
          const nextData = [...prev, { value: eegValue, time: prev.length }]
          if (nextData.length > MAX_DATA_POINTS) {
            nextData.shift()
          }
          return nextData
        })
      }
    }

    ws.current.onclose = () => {
      console.log('WebSocket disconnected')
    }

    return () => {
      ws.current.close()
    }
  }, [])

  return (
    <Box
      sx={{
        minHeight: '100vh',
        p: 4,
        bg: 'background',
        color: 'text',
        fontFamily: 'heading',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <Heading as="h1" mb={4}>
        Real-time EEG Wave Visualization
      </Heading>
      {data.length === 0 ? (
        <Text>Waiting for data...</Text>
      ) : (
        <ResponsiveContainer width="90%" height={400}>
          <LineChart data={data}>
            <CartesianGrid stroke="#333" />
            <XAxis dataKey="time" tick={{ fill: '#eee' }} />
            <YAxis tick={{ fill: '#eee' }} domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ backgroundColor: '#222', border: 'none' }}
              labelStyle={{ color: '#fff' }}
              itemStyle={{ color: '#0af' }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#0af"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Box>
  )
}

export default App
